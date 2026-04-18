# Card Kingdom Buylist Scraper

## Problem: 403 Forbidden Errors

Card Kingdom has anti-bot protection that blocks basic HTTP scraping with `requests`. When you try to scrape, you'll get:

```
403 Client Error: Forbidden for url: https://www.cardkingdom.com/purchasing/mtg_singles
```

## Solutions

### Option 1: Use Selenium (Recommended)
Uses a real headless Chrome browser, which bypasses anti-bot detection.

**Setup:**
```bash
# Install dependencies
pip install selenium beautifulsoup4 pandas

# Install ChromeDriver (match your Chrome version)
# https://chromedriver.chromium.org/
```

**Usage:**
```bash
python cardkingdom_scraper_selenium.py --search "Black Lotus"
python cardkingdom_scraper_selenium.py --search "Lightning Bolt" --output results.csv
python cardkingdom_scraper_selenium.py --search "Mox Pearl" --no-headless  # Show browser
```

**Pros:**
- Works reliably (uses real browser automation)
- Can handle JavaScript-rendered content
- Avoids anti-bot detection

**Cons:**
- Slower (browser startup overhead)
- Requires ChromeDriver installation
- Uses more system resources

---

### Option 2: Use Official APIs (Best Long-term)
Instead of scraping Card Kingdom, use official card databases:

**Scryfall API** (free, no key required):
```python
import requests
response = requests.get("https://api.scryfall.com/cards/search?q=name:Black%20Lotus")
cards = response.json()
```

**TCGPlayer API** (requires free key):
- Register at https://tcgplayer.com/api/
- More comprehensive pricing data
- Official support

---

### Option 3: Manual Inspection
If you only need occasional data:
1. Visit https://www.cardkingdom.com/purchasing/mtg_singles
2. Use browser DevTools (F12) to inspect network requests
3. Export data or copy-paste results

---

## File Guide

- `cardkingdom_buylist_scraper.py` - Basic requests-based scraper (limited by 403 errors)
- `cardkingdom_scraper_selenium.py` - Robust Selenium-based scraper (recommended)
- `README.md` - This file

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'selenium'"
```bash
pip install selenium
```

### "WebDriverException: chromedriver not found"
1. Download ChromeDriver from https://chromedriver.chromium.org/
2. Match the version with your Chrome browser (`chrome://version`)
3. Either:
   - Add to PATH, or
   - Edit `cardkingdom_scraper_selenium.py` line with:
     ```python
     driver = webdriver.Chrome(
         executable_path="/path/to/chromedriver",
         options=options
     )
     ```

### Still getting 403 errors even with Selenium?
- Try adding longer delays: `time.sleep(3)` between requests
- Check if Card Kingdom changed their HTML structure
- Consider using Scryfall or TCGPlayer APIs instead

---

## Legal Note

Always check website Terms of Service before scraping. Some sites prohibit automated access. For Card Kingdom specifically:
- Review: https://www.cardkingdom.com/about/legal
- Rate limiting: Use delays between requests (2+ seconds)
- Respect robots.txt guidelines
