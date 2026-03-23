#!/usr/bin/env python3
"""
Atomic Empire Buylist Scraper - Selenium Version
==================================================
Scrapes Atomic Empire (preferred local game store) for MTG card buylist prices.

Uses Selenium with Chrome headless to handle JavaScript-rendered content.

Requirements:
    pip install selenium beautifulsoup4 pandas lxml

Installation:
    1. Install chromedriver matching your Chrome version:
       https://chromedriver.chromium.org/
    2. Add chromedriver to PATH or specify its location below

Usage:
    python atomic_empire_scraper.py --search "Black Lotus"
    python atomic_empire_scraper.py --search "Lightning Bolt" --output atomic_empire_buylist.csv
    python atomic_empire_scraper.py --bulk-file card_list.txt --output atomic_empire_bulk.csv
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
from typing import List, Dict, Optional
from urllib.parse import urljoin

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_URL = "https://www.atomicempire.com"
BUYLIST_URL = "https://www.atomicempire.com/Buylist"
SEARCH_URL = "https://www.atomicempire.com/Shop"

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

def parse_product_cards(soup: BeautifulSoup) -> List[Dict]:
    """Parse card rows from Atomic Empire search/buylist results page."""
    cards = []
    
    # Try multiple selectors for different page layouts
    rows = (
        soup.select("div.product-item") or
        soup.select("div.card-product") or
        soup.select("div.inventory-row") or
        soup.select("tr.product-row") or
        soup.select("div.productItemWrapper")
    )
    
    for row in rows:
        card = _extract_card_from_element(row)
        if card:
            cards.append(card)
    
    return cards


def _extract_card_from_element(element) -> Optional[Dict]:
    """Extract card data from a single product element."""
    try:
        # ── Name ──────────────────────────────────────────────────────────────
        name_el = (
            element.select_one("a.product-name") or
            element.select_one(".product-title") or
            element.select_one("h3.card-name") or
            element.select_one("a[href*='/Shop/Details/']")
        )
        
        name = name_el.get_text(strip=True) if name_el else None
        if not name:
            return None

        # Extract product link for additional info if needed
        product_url = None
        if name_el and name_el.name == 'a':
            product_url = name_el.get('href')
            if product_url and not product_url.startswith('http'):
                product_url = urljoin(BASE_URL, product_url)

        # ── Set / Edition / Expansion ─────────────────────────────────────────
        set_el = (
            element.select_one(".set-code") or
            element.select_one(".expansion") or
            element.select_one(".set-info") or
            element.select_one("span.set")
        )
        edition = set_el.get_text(strip=True) if set_el else "Unknown"

        # ── Condition ─────────────────────────────────────────────────────────
        condition_el = (
            element.select_one(".condition") or
            element.select_one(".card-condition") or
            element.select_one("span.condition")
        )
        condition = condition_el.get_text(strip=True) if condition_el else "NM"

        # ── Foil ──────────────────────────────────────────────────────────────
        is_foil = bool(
            element.select_one(".foil") or
            element.select_one(".is-foil") or
            "foil" in name.lower()
        )

        # ── Price (Buylist Price for Atomic Empire) ────────────────────────────
        price = _extract_price(element)

        # Validate price
        if price < 0 or price > 100000:
            log.debug(f"Suspicious price for '{name}': ${price:.2f}")
            price = 0.0

        # ── Quantity Available ────────────────────────────────────────────────
        qty_el = (
            element.select_one(".quantity-available") or
            element.select_one(".stock-qty") or
            element.select_one("span.qty")
        )
        qty = qty_el.get_text(strip=True) if qty_el else "N/A"

        return {
            "name": name,
            "edition": edition,
            "condition": condition,
            "foil": is_foil,
            "buy_price": price,
            "quantity_available": qty,
            "product_url": product_url,
            "vendor": "Atomic Empire",
        }

    except Exception as exc:
        log.debug(f"Element parse error: {exc}")
        return None


def _extract_price(element) -> float:
    """Extract price from element using multiple selector strategies."""
    price_text = "$0.00"
    
    # Try various price selectors in order of likelihood
    selectors = [
        ".buy-price",
        ".buylist-price",
        ".product-price",
        ".price",
        "span.price",
        "[data-price]",
        "td.price",
    ]
    
    for selector in selectors:
        price_el = element.select_one(selector)
        if price_el:
            price_text = price_el.get_text(strip=True)
            if price_text and price_text != "$0.00":
                break
    
    # Handle case where price might be in a span within a div
    if price_text == "$0.00":
        for span in element.select("span"):
            text = span.get_text(strip=True)
            if text.startswith("$") and len(text) < 20:
                price_text = text
                break
    
    return _parse_price(price_text)


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

def scrape_by_search(query: str, headless: bool = True) -> List[Dict]:
    """Scrape Atomic Empire for cards matching search query."""
    driver = create_chrome_driver(headless=headless)
    all_cards: List[Dict] = []
    
    try:
        page = 1
        max_empty_pages = 2
        empty_count = 0
        
        while True:
            # Build URL with search parameters
            # Adjust query params based on Atomic Empire's actual URL structure
            url = f"{SEARCH_URL}?search={query}&page={page}"
            
            log.info(f"Fetching page {page}: {url}")
            driver.get(url)
            
            # Wait for content to load
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "div.product-item, div.card-product, div.productItemWrapper")
                    )
                )
                # Give JavaScript time to render prices
                time.sleep(2)
            except Exception as e:
                log.warning(f"Timeout waiting for content on page {page}: {e}")
                break
            
            # Parse the page
            soup = BeautifulSoup(driver.page_source, "lxml")
            cards = parse_product_cards(soup)
            
            if not cards:
                empty_count += 1
                log.debug(f"Page {page} returned no cards (empty count: {empty_count})")
                if empty_count >= max_empty_pages:
                    break
            else:
                empty_count = 0
                all_cards.extend(cards)
                log.info(f"Page {page}: Found {len(cards)} cards (total: {len(all_cards)})")
            
            # Check if there's a next page
            next_button = driver.find_elements(By.CSS_SELECTOR, "a[rel='next'], a.next-page")
            if not next_button:
                log.info("No next page found, stopping.")
                break
            
            page += 1
            time.sleep(3)  # Be respectful to the server
    
    finally:
        driver.quit()
    
    return all_cards


def scrape_bulk_list(card_list: List[str], headless: bool = True) -> List[Dict]:
    """Scrape Atomic Empire for multiple cards from a list."""
    all_cards: List[Dict] = []
    
    for i, card_name in enumerate(card_list, 1):
        log.info(f"Processing card {i}/{len(card_list)}: {card_name}")
        cards = scrape_by_search(card_name, headless=headless)
        all_cards.extend(cards)
        
        # Be respectful and don't hammer the server
        if i < len(card_list):
            time.sleep(5)
    
    return all_cards


# ── Output ────────────────────────────────────────────────────────────────────

def display_results(cards: List[Dict]) -> None:
    """Pretty-print results to stdout."""
    if not cards:
        print("No cards found.")
        return
    
    df = pd.DataFrame(cards)
    df = df.sort_values("buy_price", ascending=False)
    
    print(f"\n{'='*90}")
    print(f"  Atomic Empire Buylist Results — {len(df)} card(s) found")
    print(f"{'='*90}")
    
    # Display relevant columns
    display_cols = ["name", "edition", "condition", "foil", "buy_price", "quantity_available"]
    display_cols = [col for col in display_cols if col in df.columns]
    
    print(df[display_cols].to_string(index=False))
    print()


def save_results(cards: List[Dict], filepath: str) -> None:
    """Save results to CSV."""
    if not cards:
        log.warning("No cards to save")
        return
    
    df = pd.DataFrame(cards)
    df = df.sort_values("buy_price", ascending=False)
    df.to_csv(filepath, index=False)
    log.info(f"Results saved to {filepath} ({len(df)} cards)")


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Scrape Atomic Empire buylist prices using Selenium.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--search", metavar="CARD_NAME",
                   help='Search for a specific card, e.g. --search "Black Lotus"')
    p.add_argument("--bulk-file", metavar="FILE",
                   help="File with one card name per line to bulk scrape")
    p.add_argument("--output", "-o", metavar="FILE", default="atomic_empire_buylist.csv",
                   help="Save results to this CSV file (default: atomic_empire_buylist.csv)")
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
    
    # Validate input
    if not args.search and not args.bulk_file:
        parser.print_help()
        sys.exit(1)
    
    log.info("Starting Selenium-based Atomic Empire scraper...")
    
    # Scrape based on input method
    if args.search:
        cards = scrape_by_search(args.search, headless=not args.no_headless)
    else:
        # Load card list from file
        try:
            with open(args.bulk_file, 'r') as f:
                card_list = [line.strip() for line in f if line.strip()]
            log.info(f"Loaded {len(card_list)} cards from {args.bulk_file}")
            cards = scrape_bulk_list(card_list, headless=not args.no_headless)
        except FileNotFoundError:
            log.error(f"File not found: {args.bulk_file}")
            sys.exit(1)
    
    if not cards:
        log.warning("No cards found. Check your search query or network connection.")
        sys.exit(1)
    
    # Save results
    save_results(cards, args.output)
    display_results(cards)


if __name__ == "__main__":
    main()
