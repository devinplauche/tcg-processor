#!/usr/bin/env python3
"""
Card Kingdom Buylist Scraper - Selenium Version
================================================
Uses Selenium with Chrome headless to bypass anti-bot protection.

This version uses a real browser (headless chromium) to scrape Card Kingdom,
which avoids the 403 Forbidden errors from the basic requests version.

Requirements:
    pip install selenium beautifulsoup4 pandas

Installation:
    1. Install chromedriver matching your Chrome version:
       https://chromedriver.chromium.org/
    2. Add chromedriver to PATH or specify its location below

Usage:
    python cardkingdom_scraper_selenium.py --search "Black Lotus"
    python cardkingdom_scraper_selenium.py --search "Lightning Bolt" --output results.csv
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import argparse
import logging
import sys
from urllib.parse import urljoin, quote_plus

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_URL = "https://www.cardkingdom.com"
BUYLIST_URL = "https://www.cardkingdom.com/purchasing/mtg_singles"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Selenium Driver Setup ──────────────────────────────────────────────────────

def create_chrome_driver(headless: bool = True) -> webdriver.Chrome:
    """Create a Chrome webdriver with anti-detection optimizations."""
    options = webdriver.ChromeOptions()
    
    if headless:
        options.add_argument("--headless=new")
    
    # Anti-detection arguments
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # User agent that looks realistic
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Network optimization
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        log.error("Failed to create Chrome driver: %s", e)
        log.error("Make sure chromedriver is installed and in PATH")
        sys.exit(1)
    
    return driver


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_buylist_cards(soup: BeautifulSoup) -> list[dict]:
    """Parse card rows from a Card Kingdom buylist results page."""
    cards = []
    
    # Find all product rows (this selector may need adjustment based on current HTML)
    rows = soup.select("table.buylisting tbody tr") or soup.select("div.productItemWrapper")
    
    for row in rows:
        card = _extract_card_from_row(row)
        if card:
            cards.append(card)
    
    return cards


def _extract_card_from_row(row) -> dict | None:
    """Extract card data from a single table row or card block."""
    try:
        # ── Name ──────────────────────────────────────────────────────────────
        name_el = (
            row.select_one("td.productDesc span.productDetailTitle")
            or row.select_one(".productDetailTitle")
            or row.select_one("a.card-name")
            or row.select_one("a[href*='/purchasing/search']")
        )
        name = name_el.get_text(strip=True) if name_el else None
        if not name:
            return None

        # ── Set / Edition ─────────────────────────────────────────────────────
        set_el = (
            row.select_one("td.productDesc span.productDetailSet")
            or row.select_one(".productDetailSet")
            or row.select_one(".card-set")
        )
        edition = set_el.get_text(strip=True) if set_el else "Unknown"

        # ── Condition ─────────────────────────────────────────────────────────
        condition_el = row.select_one("td.condition") or row.select_one(".condition")
        condition = condition_el.get_text(strip=True) if condition_el else "NM"

        # ── Buylist price - try multiple selectors ────────────────────────────
        price_el = None
        price_text = "$0.00"
        
        # Try various price selectors in order of likelihood
        selectors = [
            "td.sellPrice",
            ".sellPrice",
            "span.price",
            ".buylist-price",
            "td[data-price]",
            "td:nth-child(4)",  # Fallback to 4th column
        ]
        
        for selector in selectors:
            price_el = row.select_one(selector)
            if price_el:
                price_text = price_el.get_text(strip=True)
                if price_text and price_text != "$0.00":
                    break
        
        # Handle case where price might be in a span within the cell
        if price_text == "$0.00":
            price_spans = row.select("span")
            for span in price_spans:
                text = span.get_text(strip=True)
                if text.startswith("$"):
                    price_text = text
                    break
        
        price = _parse_price(price_text)

        # Validate price
        if price < 0 or price > 100000:
            log.debug(f"Suspicious price for '{name}': ${price:.2f}")
            price = 0.0

        # ── Max qty Card Kingdom will buy ────────────────────────────────────
        qty_el = row.select_one("td.qtyMax") or row.select_one(".qtyMax")
        qty = qty_el.get_text(strip=True) if qty_el else "N/A"

        return {
            "name": name,
            "edition": edition,
            "condition": condition,
            "foil": bool(row.select_one(".foil") or "foil" in name.lower()),
            "buy_price": price,
            "max_qty": qty,
        }

    except Exception as exc:
        log.debug(f"Row parse error: {exc}")
        return None


def _parse_price(text: str) -> float:
    """Convert a price string like '$3.50' to a float."""
    if not text or not isinstance(text, str):
        return 0.0
    cleaned = text.replace("$", "").replace(",", "").strip()
    try:
        value = float(cleaned)
        return max(0.0, value)
    except ValueError:
        log.debug("Could not parse price: %s", text)
        return 0.0


# ── Main Scraping Function ─────────────────────────────────────────────────────

def scrape_search_selenium(query: str, headless: bool = True) -> list[dict]:
    """Scrape Card Kingdom buylist using Selenium."""
    driver = create_chrome_driver(headless=headless)
    all_cards: list[dict] = []
    
    try:
        page = 1
        max_empty_pages = 2
        empty_count = 0
        
        while True:
            # Build URL with search parameters
            encoded_query = quote_plus(query)
            url = f"{BUYLIST_URL}?filter[search]={encoded_query}&page={page}"
            
            log.info(f"Fetching page {page}: {url}")
            driver.get(url)
            
            # Wait for content to load
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table.buylisting tbody tr, div.productItemWrapper"))
                )
                # Give JavaScript time to render prices
                time.sleep(2)
            except Exception as e:
                log.warning(f"Timeout waiting for content on page {page}: {e}")
                break
            
            # Parse the page
            soup = BeautifulSoup(driver.page_source, "lxml")
            cards = parse_buylist_cards(soup)
            
            if not cards:
                empty_count += 1
                log.debug(f"Page {page} returned no cards (empty count: {empty_count})")
                if empty_count > max_empty_pages:
                    break
            else:
                empty_count = 0
                all_cards.extend(cards)
                log.info(f"Page {page}: Found {len(cards)} cards (total: {len(all_cards)})")
            
            # Check if there's a next page
            next_button = driver.find_elements(By.CSS_SELECTOR, "a[rel='next']")
            if not next_button:
                log.info("No next page found, stopping.")
                break
            
            page += 1
            time.sleep(3)  # Be respectful
    
    finally:
        driver.quit()
    
    return all_cards


# ── Output ────────────────────────────────────────────────────────────────────

def display_results(cards: list[dict]) -> None:
    """Pretty-print results to stdout."""
    if not cards:
        print("No cards found.")
        return
    
    df = pd.DataFrame(cards)
    df = df.sort_values("buy_price", ascending=False)
    
    print(f"\n{'='*70}")
    print(f"  Card Kingdom Buylist Results — {len(df)} card(s) found")
    print(f"{'='*70}")
    print(df.to_string(index=False))
    print()


def save_results(cards: list[dict], filepath: str) -> None:
    """Save results to CSV."""
    df = pd.DataFrame(cards)
    df = df.sort_values("buy_price", ascending=False)
    df.to_csv(filepath, index=False)
    log.info("Results saved to %s", filepath)


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Scrape Card Kingdom buylist prices using Selenium.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--search", metavar="CARD_NAME", required=True,
                   help='Search for a specific card, e.g. --search "Black Lotus"')
    p.add_argument("--output", "-o", metavar="FILE",
                   help="Save results to this CSV file (default: print to console)")
    p.add_argument("--no-headless", action="store_true",
                   help="Show the browser window (default: headless)")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Enable debug logging")
    return p


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    log.info("Starting Selenium-based Card Kingdom scraper...")
    cards = scrape_search_selenium(args.search, headless=not args.no_headless)
    
    if not cards:
        log.error("No cards found. Check your search query or browser output.")
        sys.exit(1)
    
    if args.output:
        save_results(cards, args.output)
    
    display_results(cards)


if __name__ == "__main__":
    main()
