import requests
from bs4 import BeautifulSoup
import shelve
import hashlib
import logging
import sys
from http.cookiejar import MozillaCookieJar
from urllib.parse import urlparse
import yaml

# --- Setup logging to file ---
logging.basicConfig(
    filename="train_notifier.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
    filemode="a+",
)

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# --- User configuration: exact URLs to check ---
URLS = config.get("URLS", [])
# Example:
# urls:
#   - https://grandtrain.ru/search/2078950-2000003/30.06.2025/028С/

BOT_TOKEN = config["BOT_TOKEN"]
# Example: bot_token: 1234567:secret_token_here
CHAT_IDS = config.get("CHAT_IDS", [])
# Example:
# chat_ids:
#   - 123456890

# --- User configuration: allowed seat types ---
ALLOWED_SEAT_TYPES = ["Плацкарт", "Купе"]
# Cookie storage file to persist session
COOKIE_FILE = "session_cookies.txt"


# Browser-like headers for consistent page content
def get_browser_session():
    session = requests.Session()
    jar = MozillaCookieJar(COOKIE_FILE)
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
        logging.info(f"Loaded cookies from {COOKIE_FILE}")
    except FileNotFoundError:
        logging.info(f"No existing cookie file, starting fresh: {COOKIE_FILE}")
    session.cookies = jar
    session.headers.update(
        {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Cache-Control": "max-age=0",
            "Referer": "https://grandtrain.ru/",
        }
    )
    return session


# Fetch train details page, checking for redirect or errors
def fetch_train_details(session, url):
    logging.info(f"Requesting detail URL: {url}")
    resp = session.get(url, allow_redirects=False)
    if resp.status_code == 403:
        logging.error(f"403 Forbidden for URL: {url}. Exiting.")
        sys.exit(1)
    if resp.status_code in (301, 302):
        location = resp.headers.get("Location", "")
        if location.startswith("https://grandtrain.ru/"):
            logging.info(f"No seats available, redirected for URL: {url}")
            session.cookies.save(ignore_discard=True, ignore_expires=True)
            return None
    resp = session.get(url)
    resp.raise_for_status()
    session.cookies.save(ignore_discard=True, ignore_expires=True)
    logging.info(f"Saved cookies to {COOKIE_FILE}")
    return resp.content


# Parse detailed page for seat availability
def parse_train_details(html):
    soup = BeautifulSoup(html, "html.parser")
    classes = []
    container = soup.find("div", class_="classes-container")
    if not container:
        return classes

    for car in container.find_all("div", class_="car-class"):
        car_type = car.get("data-filter", "").strip()
        if car_type not in ALLOWED_SEAT_TYPES:
            continue

        wagon_info = car.find("span", class_="car-class__car-num")
        wagons = (
            wagon_info.get_text(strip=True).replace("Вагоны:", "").strip()
            if wagon_info
            else ""
        )

        # Grab the first piece of fare info (e.g. "18 верхних")
        fare = car.find("div", class_="car-class__fare-item")
        seats_text = ""
        if fare:
            seats_span = fare.find("span")
            seats_text = seats_span.get_text(strip=True) if seats_span else ""
        logging.info(seats_text)
        # **NEW**: skip any upper-seat listing ("верхние", "верхних", etc.)
        # if "верх" in seats_text.lower():
        #    continue

        classes.append({"type": car_type, "wagons": wagons, "seats": seats_text})
    return classes


# Send Telegram message
def send_telegram_message(
    bot_token: str, chat_id: int, text: str, parse_mode: str = None
):
    logging.info(f"Sending message to chat_id {chat_id}")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    resp = requests.post(url, data=payload)
    resp.raise_for_status()
    logging.info(f"Message sent to {chat_id}")


# Utility to hash message content
def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Format output message
def format_output(results):
    lines = []
    for date, trains in results.items():
        lines.append(f"\n📅 {date}")
        if not trains:
            lines.append("🚫")
            continue
        for train_number, classes in trains.items():
            lines.append(f" ┌ 🚄 {train_number}:")
            if not classes:
                lines.append("🚫")
            for cls in classes:
                icon = "" if cls["type"] == "Купе" else ""
                lines.append(
                    f" ├─{icon}{cls['type']} | {cls['wagons']} | {cls['seats']}"
                )
    return "\n".join(lines)


if __name__ == "__main__":
    logging.info("Starting train notifier run")
    session = get_browser_session()
    results = {}

    for url in URLS:
        html = fetch_train_details(session, url)
        classes = [] if html is None else parse_train_details(html)

        # Extract date and train_number from URL path
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 4 and parts[0] == "search":
            date = parts[2]
            train_number = parts[3]
        else:
            date = "unknown"
            train_number = url

        results.setdefault(date, {})[train_number] = classes
        logging.info(f"URL {url}: processed train {train_number} for date {date}")

    # Check if any seats found at all
    total_seats = sum(
        len(classes) for date_res in results.values() for classes in date_res.values()
    )
    if total_seats == 0:
        logging.info("No seats found for any URLs. Skipping sending messages.")
        sys.exit(0)

    message = format_output(results)
    logging.info(f"Message: {message}")
    message_hash = hash_text(message)

    with shelve.open("last_message_hash.db") as db:
        for chat_id in CHAT_IDS:
            key = f"last_hash_{chat_id}"
            if db.get(key) != message_hash:
                logging.info(f"Content changed for {chat_id}, sending update")
                send_telegram_message(BOT_TOKEN, chat_id, message)
                db[key] = message_hash
            else:
                logging.info(f"No change for {chat_id}, skipping send")
    logging.info("Run complete")
