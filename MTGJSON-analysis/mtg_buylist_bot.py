#!/usr/bin/env python3
"""
MTG Buylist Spike Tracker
--------------------------
Detects when Card Kingdom raises their buylist prices significantly,
then searches TCGPlayer for local pickup copies near you.
Logs all prices to a local SQLite database and emails alerts.

Data source: MTGJSON AllPrices.json (free, updated daily)
  -> https://mtgjson.com/api/v5/AllPrices.json.gz

Flow:
  1. Download MTGJSON AllPrices.json.gz (daily, ~80MB compressed)
  2. Extract Card Kingdom buylist prices for all cards
  3. Compare today vs yesterday (stored in local SQLite DB)
  4. Flag cards where CK buylist rose >= MIN_SPIKE_PCT
  5. Search TCGPlayer for local pickup listings near your zip
  6. Email alert with best opportunities sorted by profit margin

Setup:
  pip install requests beautifulsoup4 schedule
  (sqlite3 is built into Python -- no install needed)

Database:
  All price history and alerts are stored in mtg_prices.db (auto-created).
  Query it anytime:
    sqlite3 mtg_prices.db "SELECT * FROM alerts ORDER BY date DESC LIMIT 20"
    sqlite3 mtg_prices.db "SELECT name, ck_cash, date FROM price_history WHERE name='Black Lotus'"
"""

import os
import re
import gzip
import json
import time
import sqlite3
import smtplib
import schedule
import requests
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# -------------------------------------------------------------
#  CONFIG -- Edit these values before running
# -------------------------------------------------------------
CONFIG = {
    # --- Email (Gmail App Password) ---
    "email_from":     "you@gmail.com",
    "email_password": "xxxx xxxx xxxx xxxx",   # Gmail App Password, NOT your login password
    "email_to":       "you@gmail.com",

    # --- Database ---
    "db_file": "mtg_prices.db",   # SQLite file, created automatically on first run

    # --- Location ---
    "zip_code": "10001",   # Your zip code for TCGPlayer local pickup search

    # --- Thresholds ---
    "min_buylist_spike_pct": 50,    # Alert when CK buylist rises >= this % overnight
    "min_buylist_price":     1.50,  # Ignore cards CK pays less than this
    "min_profit_usd":        2.00,  # Min profit to highlight in email

    # --- Data ---
    "prices_url": "https://mtgjson.com/api/v5/AllPrices.json.gz",
    "cache_file": "allprices_cache.json.gz",   # Reused within same day

    # --- Schedule ---
    "check_time": "08:00",   # Daily run time (24h format)

    # --- Limits ---
    "max_alerts_per_run": 25,
    "request_delay":      1.5,
}

HEADERS = {"User-Agent": "MTGBuylistBot/1.0 (personal arbitrage tool)"}


# -------------------------------------------------------------
#  SQLITE HELPERS
# -------------------------------------------------------------
def get_db():
    """Return a connection to the SQLite database, creating tables if needed."""
    conn = sqlite3.connect(CONFIG["db_file"])
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS price_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            uuid        TEXT NOT NULL,
            name        TEXT,
            set_code    TEXT,
            ck_cash     REAL,
            ck_credit   REAL,
            UNIQUE(date, uuid)
        );

        CREATE INDEX IF NOT EXISTS idx_price_date ON price_history(date);
        CREATE INDEX IF NOT EXISTS idx_price_uuid ON price_history(uuid);

        CREATE TABLE IF NOT EXISTS alerts (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            date                 TEXT NOT NULL,
            name                 TEXT,
            set_code             TEXT,
            ck_buylist_yesterday REAL,
            ck_buylist_today     REAL,
            spike_pct            REAL,
            tcg_local_price      REAL,
            est_profit           REAL,
            tcg_store            TEXT,
            tcg_url              TEXT
        );
    """)
    conn.commit()
    return conn


def load_yesterday_prices(conn):
    """
    Return prices from the most recent date in the DB as:
      { uuid: {"name": str, "set": str, "ck_buylist": float} }
    """
    cur = conn.cursor()
    cur.execute("SELECT MAX(date) as latest FROM price_history")
    row = cur.fetchone()
    if not row or not row["latest"]:
        return {}

    latest = row["latest"]
    cur.execute(
        "SELECT uuid, name, set_code, ck_cash FROM price_history WHERE date = ?",
        (latest,)
    )
    result = {
        r["uuid"]: {"name": r["name"], "set": r["set_code"], "ck_buylist": r["ck_cash"]}
        for r in cur.fetchall() if r["ck_cash"]
    }
    log(f"Loaded {len(result):,} yesterday prices from DB (date: {latest})")
    return result


def save_today_prices(conn, prices_today):
    """Bulk-insert today's prices into price_history, skipping duplicates."""
    today_str = str(date.today())
    rows = [
        (today_str, uuid, d["name"], d["set"], d["ck_cash"], d.get("ck_credit"))
        for uuid, d in prices_today.items()
    ]
    conn.executemany(
        """INSERT OR IGNORE INTO price_history
           (date, uuid, name, set_code, ck_cash, ck_credit)
           VALUES (?, ?, ?, ?, ?, ?)""",
        rows
    )
    conn.commit()
    log(f"Saved {len(rows):,} prices to DB for {today_str}")


def log_alert(conn, alert):
    """Insert a single alert/opportunity into the alerts table."""
    conn.execute(
        """INSERT INTO alerts
           (date, name, set_code, ck_buylist_yesterday, ck_buylist_today,
            spike_pct, tcg_local_price, est_profit, tcg_store, tcg_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(date.today()),
            alert.get("name"),
            alert.get("set"),
            alert.get("ck_yesterday"),
            alert.get("ck_today"),
            alert.get("spike_pct"),
            alert.get("tcg_price"),
            alert.get("profit"),
            alert.get("store_name"),
            alert.get("tcg_url"),
        )
    )
    conn.commit()


# -------------------------------------------------------------
#  STEP 1: Download MTGJSON AllPrices (with daily cache)
# -------------------------------------------------------------
def download_prices():
    """
    Download AllPrices.json.gz from MTGJSON.
    Reuses a local cache if already downloaded today.
    Returns the parsed data dict.
    """
    cache = CONFIG["cache_file"]
    today_str = str(date.today())

    if os.path.exists(cache):
        mtime = datetime.fromtimestamp(os.path.getmtime(cache)).date()
        if str(mtime) == today_str:
            log("Using cached AllPrices.json from today")
            with gzip.open(cache, "rt", encoding="utf-8") as f:
                return json.load(f)["data"]

    log("Downloading AllPrices.json.gz from MTGJSON (~80MB)...")
    resp = requests.get(CONFIG["prices_url"], headers=HEADERS, stream=True, timeout=120)
    resp.raise_for_status()

    with open(cache, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    log("Download complete, parsing...")
    with gzip.open(cache, "rt", encoding="utf-8") as f:
        data = json.load(f)["data"]

    log(f"Loaded prices for {len(data):,} card printings")
    return data


# -------------------------------------------------------------
#  STEP 2: Fetch card name/set lookup from MTGJSON
# -------------------------------------------------------------
def fetch_card_names():
    """Returns { uuid: {"name": str, "set": str} } from AllIdentifiers.json.gz"""
    url   = "https://mtgjson.com/api/v5/AllIdentifiers.json.gz"
    cache = "allidentifiers_cache.json.gz"
    today_str = str(date.today())

    if os.path.exists(cache):
        mtime = datetime.fromtimestamp(os.path.getmtime(cache)).date()
        if str(mtime) == today_str:
            log("Using cached AllIdentifiers.json")
            with gzip.open(cache, "rt", encoding="utf-8") as f:
                raw = json.load(f)["data"]
            return {u: {"name": v.get("name", "?"), "set": v.get("setCode", "?")}
                    for u, v in raw.items()}

    log("Downloading AllIdentifiers.json.gz (~30MB)...")
    resp = requests.get(url, headers=HEADERS, stream=True, timeout=120)
    resp.raise_for_status()
    with open(cache, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)

    with gzip.open(cache, "rt", encoding="utf-8") as f:
        raw = json.load(f)["data"]

    result = {u: {"name": v.get("name", "?"), "set": v.get("setCode", "?")}
              for u, v in raw.items()}
    log(f"Loaded {len(result):,} card identifiers")
    return result


# -------------------------------------------------------------
#  STEP 3: Extract CK buylist prices from MTGJSON data
# -------------------------------------------------------------
def extract_ck_buylists(all_prices, card_names):
    """
    Parse MTGJSON AllPrices and extract CK buylist cash prices.
    Returns { uuid: {name, set, ck_cash, ck_credit} }

    MTGJSON structure:
      allPrices[uuid]["paper"]["cardkingdom"]["buylist"]["normal"][date] = price
    """
    results = {}

    for uuid, price_data in all_prices.items():
        bl = (price_data
              .get("paper", {})
              .get("cardkingdom", {})
              .get("buylist", {}))

        normal = bl.get("normal", {})
        foil   = bl.get("foil", {})

        if not normal:
            continue

        latest_cash = normal[max(normal.keys())]
        latest_credit = foil[max(foil.keys())] if foil else None

        if latest_cash and float(latest_cash) >= CONFIG["min_buylist_price"]:
            info = card_names.get(uuid, {"name": "Unknown", "set": "?"})
            results[uuid] = {
                "name":      info["name"],
                "set":       info["set"],
                "ck_cash":   round(float(latest_cash), 2),
                "ck_credit": round(float(latest_credit), 2) if latest_credit else None,
            }

    log(f"Found {len(results):,} cards with CK buylist >= ${CONFIG['min_buylist_price']}")
    return results


# -------------------------------------------------------------
#  STEP 4: Detect buylist spikes vs yesterday
# -------------------------------------------------------------
def detect_spikes(today_prices, yesterday_prices):
    """Compare today vs yesterday, return cards that jumped >= threshold."""
    spikes = []

    for uuid, today in today_prices.items():
        prev = yesterday_prices.get(uuid)
        if not prev or not prev["ck_buylist"] or prev["ck_buylist"] <= 0:
            continue

        pct = ((today["ck_cash"] - prev["ck_buylist"]) / prev["ck_buylist"]) * 100

        if pct >= CONFIG["min_buylist_spike_pct"]:
            spikes.append({
                "uuid":         uuid,
                "name":         today["name"],
                "set":          today["set"],
                "ck_yesterday": round(prev["ck_buylist"], 2),
                "ck_today":     today["ck_cash"],
                "ck_credit":    today.get("ck_credit"),
                "spike_pct":    round(pct, 1),
            })

    spikes.sort(key=lambda x: x["spike_pct"], reverse=True)
    log(f"Detected {len(spikes)} buylist spikes >= {CONFIG['min_buylist_spike_pct']}%")
    return spikes[:CONFIG["max_alerts_per_run"]]


# -------------------------------------------------------------
#  STEP 5: Search TCGPlayer for local pickup
# -------------------------------------------------------------
def search_tcg_local(card_name, zip_code):
    """Search TCGPlayer for NM local pickup listings near zip_code."""
    from bs4 import BeautifulSoup
    encoded = requests.utils.quote(card_name)
    url = (
        f"https://www.tcgplayer.com/search/magic/product"
        f"?q={encoded}&Location={zip_code}&ship=local&condition=Near+Mint"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        for card in soup.select(".search-result, .product-card"):
            price_el = card.select_one(".inventory__price-with-shipping, .product-card__market-price")
            store_el = card.select_one(".seller-name, .store-name")
            if price_el:
                match = re.search(r"[\d.]+", price_el.get_text().replace(",", ""))
                if match:
                    results.append({
                        "price":      float(match.group()),
                        "store_name": store_el.get_text(strip=True) if store_el else "Local Store",
                        "url":        url,
                    })

        if results:
            return min(results, key=lambda x: x["price"])

    except Exception as e:
        log(f"  TCGPlayer local search failed for '{card_name}': {e}")

    return None


# -------------------------------------------------------------
#  STEP 6: Send email alert
# -------------------------------------------------------------
def send_email(opportunities):
    if not opportunities:
        return

    n = len(opportunities)
    subject = f"MTG Buylist Spike Alert -- {n} opportunit{'y' if n==1 else 'ies'}! [{now()}]"

    rows_html = ""
    for o in opportunities:
        has_local   = o.get("tcg_price") is not None
        profit      = o.get("profit")
        p_color     = "#2e7d32" if profit and profit >= 5 else "#f57c00" if profit and profit >= 2 else "#555"
        local_cell  = (
            f'<a href="{o["tcg_url"]}" style="color:#1565c0;">'
            f'${o["tcg_price"]:.2f} -- {o["store_name"]}</a>'
            if has_local else
            '<span style="color:#aaa;">No local listing found</span>'
        )
        profit_cell = f'<strong style="color:{p_color};">${profit:.2f}</strong>' if profit else "--"
        credit_cell = f'${o["ck_credit"]:.2f} credit' if o.get("ck_credit") else "--"

        rows_html += f"""
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:10px 8px;"><strong>{o['name']}</strong><br>
            <small style="color:#888;">{o['set']}</small></td>
          <td style="padding:10px 8px;text-align:center;">
            <span style="color:#888;">${o['ck_yesterday']:.2f}</span>
            &rarr; <strong style="color:#c62828;">${o['ck_today']:.2f}</strong><br>
            <small style="color:#c62828;">+{o['spike_pct']:.0f}%</small></td>
          <td style="padding:10px 8px;text-align:center;">{credit_cell}</td>
          <td style="padding:10px 8px;">{local_cell}</td>
          <td style="padding:10px 8px;text-align:center;">{profit_cell}</td>
        </tr>"""

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:750px;margin:auto;padding:20px;">
      <h2 style="color:#1a237e;">MTG Buylist Spike Alert</h2>
      <p style="color:#555;">Card Kingdom raised their buylist on these cards overnight.<br>
      Strategy: find cheap copies via TCGPlayer local pickup near {CONFIG['zip_code']} &rarr; sell to CK.</p>
      <table style="width:100%;border-collapse:collapse;margin-top:16px;font-size:14px;">
        <thead><tr style="background:#1a237e;color:white;text-align:left;">
          <th style="padding:10px 8px;">Card</th>
          <th style="padding:10px 8px;text-align:center;">CK Buylist Change</th>
          <th style="padding:10px 8px;text-align:center;">CK Credit</th>
          <th style="padding:10px 8px;">Cheapest Local (TCGPlayer)</th>
          <th style="padding:10px 8px;text-align:center;">Est. Profit</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      <div style="margin-top:20px;padding:14px;background:#e8f5e9;border-left:4px solid #43a047;border-radius:4px;">
        <strong>Tips:</strong>
        <ul style="margin:8px 0;padding-left:20px;color:#555;font-size:13px;">
          <li>Call your LGS -- they may match or beat TCGPlayer local prices</li>
          <li>CK credit pays ~30% more than cash -- use it if you buy from CK too</li>
          <li>Verify CK buylist quantity &gt; 0 before purchasing (they update daily)</li>
          <li>NM condition only -- CK grades strictly</li>
        </ul>
        <small style="color:#888;">Est. profit = CK cash buylist minus local buy price. Not financial advice.</small>
      </div>
      <p style="margin-top:16px;font-size:12px;color:#aaa;">
        Full history in mtg_prices.db -- query with:<br>
        <code>sqlite3 mtg_prices.db "SELECT * FROM alerts ORDER BY date DESC LIMIT 20"</code>
      </p>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = CONFIG["email_from"]
    msg["To"]      = CONFIG["email_to"]
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(CONFIG["email_from"], CONFIG["email_password"])
            server.sendmail(CONFIG["email_from"], CONFIG["email_to"], msg.as_string())
        log(f"Email sent ({n} opportunities)")
    except Exception as e:
        log(f"Email failed: {e}")


# -------------------------------------------------------------
#  MAIN
# -------------------------------------------------------------
def log(msg):
    print(f"[{now()}] {msg}")

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def run_check():
    log("=" * 55)
    log("Starting MTG Buylist Spike Check")
    log("=" * 55)

    conn = get_db()
    log(f"Database: {os.path.abspath(CONFIG['db_file'])}")

    yesterday_prices = load_yesterday_prices(conn)
    all_prices       = download_prices()
    card_names       = fetch_card_names()
    today_prices     = extract_ck_buylists(all_prices, card_names)

    save_today_prices(conn, today_prices)

    if not yesterday_prices:
        log("No previous prices found -- run again tomorrow to start detecting spikes.")
        log("Today's prices saved as baseline.")
        conn.close()
        return

    spikes = detect_spikes(today_prices, yesterday_prices)

    if not spikes:
        log("No significant buylist spikes today.")
        conn.close()
        return

    opportunities = []
    for spike in spikes:
        log(f"  {spike['name']} (+{spike['spike_pct']:.0f}%) -- searching local TCG...")
        time.sleep(CONFIG["request_delay"])

        local  = search_tcg_local(spike["name"], CONFIG["zip_code"])
        profit = round(spike["ck_today"] - local["price"], 2) if local else None

        opp = {
            **spike,
            "tcg_price":  local["price"]      if local else None,
            "store_name": local["store_name"] if local else None,
            "tcg_url":    local["url"]        if local else None,
            "profit":     profit,
        }
        opportunities.append(opp)
        log_alert(conn, opp)

    conn.close()

    opportunities.sort(key=lambda x: (x["profit"] is None, -(x["profit"] or 0)))
    profitable = [o for o in opportunities if o["profit"] and o["profit"] >= CONFIG["min_profit_usd"]]

    log(f"{len(profitable)} profitable (>= ${CONFIG['min_profit_usd']}), {len(opportunities)} total logged to DB")
    send_email(opportunities[:CONFIG["max_alerts_per_run"]])
    log("Check complete.")
    log("=" * 55)


if __name__ == "__main__":
    print("=" * 55)
    print("  MTG Buylist Spike Tracker (SQLite edition)")
    print("=" * 55)
    print(f"  Spike threshold:  >={CONFIG['min_buylist_spike_pct']}% buylist increase")
    print(f"  Min buylist:      >=${CONFIG['min_buylist_price']}")
    print(f"  Zip code:         {CONFIG['zip_code']}")
    print(f"  Daily check at:   {CONFIG['check_time']}")
    print(f"  Database:         {CONFIG['db_file']}")
    print(f"  Alerting:         {CONFIG['email_to']}")
    print("=" * 55 + "\n")

    run_check()  # Run immediately on launch

    schedule.every().day.at(CONFIG["check_time"]).do(run_check)
    while True:
        schedule.run_pending()
        time.sleep(60)