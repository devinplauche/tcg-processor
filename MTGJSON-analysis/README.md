# MTG Buylist Spike Tracker 🃏

Automatically detects when Card Kingdom raises their buylist prices overnight, 
finds cheap copies via TCGPlayer local pickup near you, and emails alerts.

---

## How It Works

```
Daily at 8am:
  1. Downloads MTGJSON AllPrices.json (Card Kingdom buylist data, 90-day history)
  2. Compares today's CK buylist prices to yesterday's (stored in Google Sheets)
  3. Flags cards where CK raised their buylist ≥ 50% overnight
  4. Searches TCGPlayer for local pickup listings near your zip code
  5. Emails you: "CK now pays $12 for Card X — local store has it for $3 → $9 profit"
  6. Logs everything to Google Sheets for your records
```

**Why buylist tracking beats retail price tracking:**
- CK raising their buylist is a *leading* signal — retail prices often haven't caught up yet
- You can buy locally at old prices before stores update
- CK credit pays ~30% more than cash — use it if you shop at CK too

---

## Setup (One Time)

### 1. Install dependencies
```bash
pip install requests beautifulsoup4 gspread google-auth schedule
```

### 2. Set up Google Sheets API

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (e.g. "MTG Bot")
3. Enable **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin → Service Accounts** → Create Service Account
5. Give it any name, click through, then create a JSON key
6. Download the JSON key and save it as `google_creds.json` in this folder
7. Create a new [Google Sheet](https://sheets.google.com)
8. Share the sheet with the service account email (from the JSON file, looks like `name@project.iam.gserviceaccount.com`)
9. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/` **THIS_PART** `/edit`

### 3. Set up Gmail App Password

1. Enable 2FA on your Google account
2. Go to [myaccount.google.com](https://myaccount.google.com) → Security → App Passwords
3. Create an App Password for "Mail"
4. Copy the 16-character password

### 4. Configure the bot

Edit the `CONFIG` block at the top of `mtg_buylist_bot.py`:

```python
CONFIG = {
    "email_from":     "you@gmail.com",
    "email_password": "xxxx xxxx xxxx xxxx",  # App Password here
    "email_to":       "you@gmail.com",
    "sheet_id":       "YOUR_SHEET_ID_HERE",   # From step 2
    "zip_code":       "10001",                # Your zip for local pickup
    "min_buylist_spike_pct": 50,              # Alert if CK buylist rises >= 50%
    "min_buylist_price":     1.50,            # Ignore cheap cards below this
    "min_profit_usd":        2.00,            # Only highlight if profit >= $2
    "check_time":            "08:00",         # Run daily at 8am
}
```

### 5. Run it

```bash
python mtg_buylist_bot.py
```

On first run it will download ~100MB of MTGJSON data and save today's prices as 
your baseline. **No spikes will be detected on day 1** — you need at least 2 days 
of data. From day 2 onwards, you'll get alerts every morning.

---

## Google Sheet Structure

The bot creates two tabs automatically:

**Price History** — daily CK buylist prices for every card
| date | uuid | name | set | ck_buylist_cash | ck_buylist_credit |
|------|------|------|-----|-----------------|-------------------|

**Alerts Log** — every spike found, with local TCGPlayer prices
| date | card_name | set | ck_buylist_yesterday | ck_buylist_today | spike_pct | tcg_local_price | est_profit | tcg_store | tcg_url |
|------|-----------|-----|----------------------|------------------|-----------|-----------------|------------|-----------|---------|

---

## Tips

- **CK credit > cash**: CK typically offers 30% more in store credit than cash. 
  If you buy cards from CK anyway, take the credit — it makes every flip more profitable.
- **Call before you drive**: TCGPlayer local pickup requires the store to confirm. 
  Call ahead or check their stock directly.
- **NM condition only**: CK grades strictly. LP copies will be paid at a lower rate.
- **Watch for quantity limits**: CK caps how many of each card they'll buy. 
  Don't buy 20 copies before checking their quantity limit.

---

## Tuning

| Setting | Default | Notes |
|---------|---------|-------|
| `min_buylist_spike_pct` | 50% | Lower = more alerts, higher = only big moves |
| `min_buylist_price` | $1.50 | Ignore cheap bulk — not worth the effort |
| `min_profit_usd` | $2.00 | Minimum profit to highlight in email |
| `check_time` | "08:00" | MTGJSON updates overnight, 8am is safe |
| `max_alerts_per_run` | 25 | Cap emails to avoid noise |

---

## Known Limitations

- **MTGJSON CK data caveat**: MTGJSON sometimes includes CK buylist prices even 
  when CK's quantity is 0 (they're not actually buying). Always verify the CK 
  buylist directly before purchasing.
- **TCGPlayer local search**: TCGPlayer's local pickup filtering can be inconsistent. 
  If no local listing is found, check TCGPlayer manually — it may still exist.
- **Day 1 = baseline only**: No spike detection on first run. Day 2+ works normally.
