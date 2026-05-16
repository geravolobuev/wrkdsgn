# Telegram Jobs Aggregator (Free Stack)

## 1) Local first run (one time)

```bash
cp .env.example .env
# fill .env with your values
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

On first run, Telethon will ask for login code. After success, file `telegram_session.session` appears.

## 2) Add Telethon session to GitHub secret

```bash
base64 telegram_session.session
```

Copy output and save as repository secret `TELETHON_SESSION_B64`.

## 3) Run in GitHub Actions

- Open `Actions` tab
- Choose `Scrape Telegram Jobs`
- Click `Run workflow`

Then schedule runs every 15 minutes automatically.
