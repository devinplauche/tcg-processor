#!/usr/bin/env python3
"""
MTG Buylist Spike Detector - Multi-Timeline Historical Analysis
Uses AllPrices.json historical data to detect spikes across timelines.
Compares different dates within the same dataset.
"""

import json
import gzip
import sqlite3
from datetime import date, timedelta
import sys
import os

# CONFIG
CONFIG = {
    "min_buylist_spike_pct": 50,    # Alert when CK buylist rises >= this %
    "min_buylist_price":     1.50,  # Ignore cards CK pays less than this
    "db_file": "mtg_prices.db",
}

# Timeline definitions (in days)
TIMELINES = {
    "week": 7,
    "month": 30,
    "3month": 90,
}

HEADERS = {"User-Agent": "MTGBuylistBot/1.0"}


def load_json_file(filepath):
    """Load JSON file, handling gzip if needed."""
    if filepath.endswith('.gz'):
        with gzip.open(filepath, 'rt', encoding='utf-8') as f:
            return json.load(f)
    else:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


def ensure_tables(conn):
    """Create database tables if they don't exist."""
    conn.executescript("""
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
            compare_date         TEXT NOT NULL,
            baseline_date        TEXT NOT NULL,
            timeline             TEXT NOT NULL,
            name                 TEXT,
            set_code             TEXT,
            collector_number     TEXT,
            ck_buylist_baseline  REAL,
            ck_buylist_compare   REAL,
            spike_pct            REAL,
            dollar_increase      REAL
        );
    """)
    conn.commit()


def extract_ck_prices(data, target_date=None):
    """
    Extract CK buylist prices from MTGJSON data.
    If target_date is None, uses the latest date for each card.
    Returns { uuid: {ck_cash, ck_credit} }
    """
    results = {}
    
    if isinstance(data, dict) and 'data' in data:
        data = data['data']
    
    for uuid, price_data in data.items():
        bl = (price_data
              .get("paper", {})
              .get("cardkingdom", {})
              .get("buylist", {}))
        
        # Get normal (non-foil) price
        normal = bl.get("normal", {})
        if not normal:
            continue
        
        # If target_date specified, use that; otherwise use latest
        if target_date:
            if target_date not in normal:
                continue
            latest_cash = float(normal[target_date])
        else:
            latest_date = max(normal.keys())
            latest_cash = float(normal[latest_date])
        
        if latest_cash >= CONFIG["min_buylist_price"]:
            foil = bl.get("foil", {})
            latest_credit = None
            if foil:
                if target_date and target_date in foil:
                    latest_credit = float(foil[target_date])
                elif not target_date:
                    foil_date = max(foil.keys())
                    latest_credit = float(foil[foil_date])
            
            results[uuid] = {
                "ck_cash": round(latest_cash, 2),
                "ck_credit": round(latest_credit, 2) if latest_credit else None,
            }
    
    return results


def fetch_card_names():
    """Load card names from cached AllIdentifiers."""
    try:
        data = load_json_file("allidentifiers_cache.json.gz")
        if isinstance(data, dict) and 'data' in data:
            data = data['data']
        
        return {u: {
                    "name": v.get("name", "?"), 
                    "set": v.get("setCode", "?"),
                    "number": v.get("number", "?")
                }
                for u, v in data.items()}
    except Exception as e:
        print(f"Error loading identifiers: {e}")
        return {}


def get_available_dates(data):
    """Get all available dates from the price data."""
    all_dates = set()
    
    if isinstance(data, dict) and 'data' in data:
        data = data['data']
    
    for card in data.values():
        bl = (card
              .get("paper", {})
              .get("cardkingdom", {})
              .get("buylist", {})
              .get("normal", {}))
        if bl:
            all_dates.update(bl.keys())
    
    return sorted(all_dates)


def detect_spikes(baseline_prices, compare_prices, card_names, timeline_name="day"):
    """Compare baseline vs compare prices and detect spikes."""
    spikes = []
    
    for uuid, compare in compare_prices.items():
        prev = baseline_prices.get(uuid)
        if not prev or not prev.get("ck_cash") or prev["ck_cash"] <= 0:
            continue
        
        pct = ((compare["ck_cash"] - prev["ck_cash"]) / prev["ck_cash"]) * 100
        dollar_increase = round(compare["ck_cash"] - prev["ck_cash"], 2)
        
        if pct >= CONFIG["min_buylist_spike_pct"]:
            info = card_names.get(uuid, {"name": "Unknown", "set": "?", "number": "?"})
            spikes.append({
                "uuid":         uuid,
                "name":         info["name"],
                "set":          info["set"],
                "number":       info["number"],
                "ck_baseline":  round(prev["ck_cash"], 2),
                "ck_compare":   compare["ck_cash"],
                "ck_credit":    compare.get("ck_credit"),
                "spike_pct":    round(pct, 1),
                "dollar_increase": dollar_increase,
                "timeline":     timeline_name,
            })
    
    spikes.sort(key=lambda x: x["spike_pct"], reverse=True)
    return spikes


def save_spikes_to_db(conn, spikes, baseline_date, compare_date):
    """Save detected spikes to database."""
    for spike in spikes:
        conn.execute(
            """INSERT INTO alerts
               (compare_date, baseline_date, timeline, name, set_code, collector_number, 
                ck_buylist_baseline, ck_buylist_compare, spike_pct, dollar_increase)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                compare_date,
                baseline_date,
                spike["timeline"],
                spike["name"],
                spike["set"],
                spike["number"],
                spike["ck_baseline"],
                spike["ck_compare"],
                spike["spike_pct"],
                spike["dollar_increase"],
            )
        )
    
    conn.commit()


def print_spikes_report(spikes, timeline_label, baseline_date, compare_date):
    """Print nicely formatted spike report."""
    if not spikes:
        print(f"\n  No spikes detected for {timeline_label}")
        return
    
    print(f"\n{'='*90}")
    print(f"TOP SPIKES BY % INCREASE - {timeline_label.upper()}")
    print(f"Comparing {compare_date} vs {baseline_date}")
    print(f"{'='*90}")
    print(f"{'Card Name':<30} {'Set':<6} {'#':<6} {baseline_date:<12} {compare_date:<12} {'Change':<10}")
    print(f"{'-'*90}")
    
    for spike in spikes[:10]:
        pct_str = f"+{spike['spike_pct']:.0f}%"
        card_display = spike['name'][:29]
        print(f"{card_display:<30} {spike['set']:<6} {str(spike['number']):<6} ${spike['ck_baseline']:<11.2f} ${spike['ck_compare']:<11.2f} {pct_str:<10}")
    
    if len(spikes) > 10:
        print(f"... and {len(spikes) - 10} more spikes")
    
    # Filter for spikes with >$5 increase
    dollar_spikes = [s for s in spikes if s['dollar_increase'] > 5.0]
    dollar_spikes.sort(key=lambda x: x['dollar_increase'], reverse=True)
    
    if dollar_spikes:
        print(f"\n{'='*90}")
        print(f"TOP SPIKES BY DOLLAR INCREASE (>$5)")
        print(f"{'='*90}")
        print(f"{'Card Name':<30} {'Set':<6} {'#':<6} {baseline_date:<12} {compare_date:<12} {'$ Increase':<12}")
        print(f"{'-'*90}")
        
        for spike in dollar_spikes[:10]:
            dollar_str = f"+${spike['dollar_increase']:.2f}"
            card_display = spike['name'][:29]
            print(f"{card_display:<30} {spike['set']:<6} {str(spike['number']):<6} ${spike['ck_baseline']:<11.2f} ${spike['ck_compare']:<11.2f} {dollar_str:<12}")
        
        if len(dollar_spikes) > 10:
            print(f"... and {len(dollar_spikes) - 10} more cards with >$5 increases")


def main():
    timeline = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if timeline not in ["week", "month", "3month", "all", "fresh"]:
        print(f"Usage: {sys.argv[0]} [week|month|3month|all|fresh]")
        print(f"  week   - Spikes from last week")
        print(f"  month  - Spikes from last month")
        print(f"  3month - Spikes from last 3 months")
        print(f"  all    - All timelines (default)")
        print(f"  fresh  - Delete database and start fresh")
        sys.exit(1)
    
    # Handle fresh start
    if timeline == "fresh":
        if os.path.exists(CONFIG["db_file"]):
            confirm = input(f"Delete {CONFIG['db_file']}? (yes/no): ").strip().lower()
            if confirm == "yes":
                os.remove(CONFIG["db_file"])
                print(f"Deleted {CONFIG['db_file']}")
            else:
                print("Cancelled")
            return
        return
    
    print("=" * 90)
    print("MTG Buylist Spike Detector - Historical Analysis")
    print("=" * 90)
    print(f"Spike threshold: >={CONFIG['min_buylist_spike_pct']}% buylist increase")
    print(f"Min buylist:     >=${CONFIG['min_buylist_price']}")
    print()
    
    conn = sqlite3.connect(CONFIG["db_file"])
    conn.row_factory = sqlite3.Row
    ensure_tables(conn)
    
    print("[1] Loading card names...")
    card_names = fetch_card_names()
    print(f"    Loaded {len(card_names):,} card identifiers")
    
    print("[2] Loading AllPrices.json historical data...")
    try:
        prices_data = load_json_file("AllPrices.json")
        print(f"    Loaded {len(prices_data.get('data', {})):,} cards")
    except Exception as e:
        print(f"    ERROR: {e}")
        conn.close()
        return
    
    print("[3] Analyzing available dates...")
    available_dates = get_available_dates(prices_data)
    print(f"    Found {len(available_dates)} dates: {available_dates[0]} to {available_dates[-1]}")
    
    # Latest date is the comparison date
    latest_date = available_dates[-1]
    latest_prices = extract_ck_prices(prices_data, latest_date)
    print(f"    Latest date ({latest_date}): {len(latest_prices):,} cards with CK buylist")
    
    # Determine which timelines to check
    timelines_to_check = [timeline] if timeline != "all" else list(TIMELINES.keys())
    
    all_spikes = {}
    
    print("[4] Detecting spikes across timelines...")
    for tl in timelines_to_check:
        days = TIMELINES[tl]
        target_date = (date.fromisoformat(latest_date) - timedelta(days=days)).isoformat()
        
        # Find closest available date
        closest_date = None
        for d in reversed(available_dates):
            if d <= target_date:
                closest_date = d
                break
        
        if not closest_date:
            closest_date = available_dates[0]
        
        historical_prices = extract_ck_prices(prices_data, closest_date)
        print(f"    {tl:8s}: Comparing {latest_date} vs {closest_date} ({len(historical_prices):,} cards)")
        
        spikes = detect_spikes(historical_prices, latest_prices, card_names, tl)
        all_spikes[tl] = (spikes, closest_date, latest_date)
        print(f"    {tl:8s}: Found {len(spikes)} spikes >= {CONFIG['min_buylist_spike_pct']}%")
    
    # Print reports for each timeline
    for tl in timelines_to_check:
        spikes, baseline_date, compare_date = all_spikes[tl]
        print_spikes_report(spikes, f"{tl} ({TIMELINES[tl]} days)", baseline_date, compare_date)
    
    print("\n[5] Saving spikes to database...")
    total_saved = 0
    for tl in timelines_to_check:
        spikes, baseline_date, compare_date = all_spikes[tl]
        save_spikes_to_db(conn, spikes, baseline_date, compare_date)
        total_saved += len(spikes)
    print(f"    Saved {total_saved} spikes (database: {CONFIG['db_file']})")
    
    conn.close()
    
    print("\n" + "=" * 90)
    print("Spike detection complete!")
    print("=" * 90)


if __name__ == "__main__":
    main()
