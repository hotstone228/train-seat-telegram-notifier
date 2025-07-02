# Train Seat Notifier 🚂

This Python script automatically checks seat availability on **[https://grandtrain.ru](https://grandtrain.ru)** and sends Telegram alerts when allowed seat types (e.g. Плацкарт, Купе) are found. Designed for travelers who want real-time updates when reserved trains open up seating.

---

## ✨ Features

- ✉️ Telegram notifications for available seats
- ⌚ Skips upper berths ("верх") by default
- 🌍 Supports multiple train URLs and multiple Telegram chat IDs
- 🔐 Persistent session cookies (Mozilla format)
- 🔒 Message deduplication using SHA256 hashing
- ⚙️ Fully configurable via `config.yaml`

---

## 📆 Sample Use Case

You’re waiting for lower-berth seats to open on Train 028С from Moscow to Saint Petersburg on a specific date. Add that URL to `config.yaml`, and you’ll get a Telegram message when a lower berth appears.

---

## 📅 Configuration

Create a `config.yaml` file:

```yaml
bot_token: "123456789:your_telegram_bot_token"
chat_ids:
  - 123456789
urls:
  - https://grandtrain.ru/search/2078950-2000003/30.06.2025/028С/
```

---

## ⚡ Requirements

```bash
pip install -r requirements.txt
```

### `requirements.txt`

```
requests
beautifulsoup4\pyyaml
```

---

## ▶️ Run

```bash
python train_notifier.py
```

It will:

- Load saved cookies (if available)
- Fetch and parse seat info from each URL
- Skip upper berth seats
- Format results by date & train
- Send Telegram messages if content has changed since the last run

---

## 📊 Output Example

```
📅 30.06.2025
 └ 🚌 028С:
  ├─ Купе | 03, 07 | 18 мест
```

---

## ⚠️ Notes

- Train site content may change; ensure class names and HTML structures are current.
- The script is tuned for Russian railway seat labels.
- It skips sending the same message twice by tracking content hashes.

---

## 📄 License

MIT — free to use, modify, and share.

---

## 🙌 Contributions

PRs are welcome for:

- Optional email/SMS alerts
- Docker support for scheduled deployments
