# MTG Arbitrage Engine - Quick Start Guide

## 🎯 What This Does

The MTG Arbitrage Engine finds profitable card flipping opportunities by:
1. **Scraping** buylist/inventory prices from different vendors
2. **Comparing** prices across vendors
3. **Identifying** profitable trade routes (buy low → sell high)
4. **Reporting** the best opportunities with profit calculations

## 🚀 5-Minute Setup

### 1. Install Dependencies
```bash
cd tcg-processor
pip install -r requirements-arbitrage.txt
```

### 2. Install ChromeDriver
Download from: https://chromedriver.chromium.org/ (match your Chrome version)
Add to your system PATH, or place in the project directory.

### 3. Verify Installation
```bash
python -c "from selenium import webdriver; print('✓ Selenium OK')"
python -c "import pandas; print('✓ Pandas OK')"
```

## 💡 Usage Examples

### Example 1: Quick Single Card Search
```bash
cd buylist-updater
python atomic_empire_scraper.py --search "Black Lotus"
```

**Output:**
```
Found 2 cards matching "Black Lotus"
- Black Lotus (Alpha, NM): $1500.00
- Black Lotus (Beta, NM): $1200.00
Saved to: atomic_empire_buylist.csv
```

### Example 2: Bulk Scrape 10 Cards
Create `card_list.txt`:
```
Black Lotus
Lightning Bolt
Path to Exile
Tarmogoyf
Snapcaster Mage
Jace, the Mind Sculptor
Liliana of the Veil
Dark Confidant
Stoneforge Mystic
Temporal Manipulation
```

Run:
```bash
python atomic_empire_scraper.py --bulk-file card_list.txt
```

### Example 3: Find Arbitrage Opportunities
```bash
cd ../arbitrage-engine

# After you have CSV files from multiple vendors:
python arbitrage_engine.py \
  --sources ../buylist-updater/atomic_empire_buylist.csv \
  --destinations ../buylist-updater/cardkingdom_buylist.csv \
  --min-profit 1.00 \
  --output opportunities.csv
```

## 📊 Complete Workflow

```bash
#!/bin/bash
# Daily arbitrage check

cd ~/tcg-processor

# 1. Scrape latest prices
cd buylist-updater

echo "Scraping Atomic Empire..."
python atomic_empire_scraper.py --bulk-file ../docs/watched_cards.txt \
  --output atomic_empire_$(date +%Y%m%d).csv

echo "Scraping CardKingdom..."
python cardkingdom_scraper_selenium.py --search "Tarmogoyf" \
  --output cardkingdom_$(date +%Y%m%d).csv

# 2. Analyze for opportunities
cd ../arbitrage-engine

python arbitrage_engine.py \
  --sources ../buylist-updater/atomic_empire_*.csv \
  --destinations ../buylist-updater/cardkingdom_*.csv \
  --output today_opportunities.csv \
  --min-profit 2.00 \
  --min-margin 0.15

# 3. Show top 10
echo "=== TOP 10 OPPORTUNITIES ==="
head -11 today_opportunities.csv | tail -10
```

## 🔧 Configuration

### Adjust Vendor Costs
Edit `arbitrage_engine.py`:
```python
VENDOR_COSTS = {
    "cardkingdom": 0.50,      # Your actual shipping cost
    "atomic_empire": 2.00,    # Local pickup/delivery cost
    "tcgplayer": 0.75,        # Your seller fees
    "ebay": 2.50,             # Your eBay+PayPal fees
}
```

### Adjust Minimum Requirements
```python
MINIMUM_PROFIT = 0.50   # $0.50 minimum profit per card
MINIMUM_MARGIN = 0.10   # 10% minimum margin
```

Or use command-line args:
```bash
python arbitrage_engine.py \
  --min-profit 2.00 \      # Only show $2+ profit cards
  --min-margin 0.20        # Only show 20%+ margin
```

## 📈 Real-World Example

### Scenario
You find that Atomic Empire has cards cheaper than TCGPlayer:

| Card | Atomic Empire | TCGPlayer | Your Profit |
|------|---------------|-----------|-------------|
| Snapcaster Mage | $60.00 | $75.00 | $15.00 - $2.00 fees = **$13.00** |
| Liliana of the Veil | $45.00 | $58.00 | $13.00 - $2.00 fees = **$11.00** |

### Steps
1. **Buy** the cards from Atomic Empire (maybe in-store to avoid shipping)
2. **List** on TCGPlayer at their going rate
3. **Ship** when sold
4. **Profit** = $13 + $11 = **$24 on just 2 cards**

The arbitrage engine **automates finding these opportunities at scale**.

## 🎮 Supported Vendors

| Vendor | Status | Notes |
|--------|--------|-------|
| Atomic Empire | ✅ Ready | Preferred local store |
| CardKingdom | ✅ Ready | Existing scraper |
| TCGPlayer | 🔄 Coming | High volume seller |
| eBay | 🔄 Coming | Individual sellers |
| Scryfall API | ✅ Available | Card data & pricing |

## 🐛 Troubleshooting

### ChromeDriver Not Found
```
FileNotFoundError: [Errno 2] No such file or directory: 'chromedriver'
```
**Fix:** Download from https://chromedriver.chromium.org/ and add to PATH

### Website Changed Layout
If scraper gets 0 results:
1. Check the website in your browser
2. Open browser's DevTools (F12)
3. Find the CSS selectors for card name/price
4. Update the selectors in `atomic_empire_scraper.py`

### Timeout Errors
```
selenium.common.exceptions.TimeoutException
```
**Fix:** Increase timeout or check your internet connection
```python
WebDriverWait(driver, 20)  # Increase from 10 to 20 seconds
```

## 📚 Next Steps

1. **Expand to More Vendors**
   - Add TCGPlayer scraper
   - Add eBay scraper
   - Integrate official APIs

2. **Automate Monitoring**
   - Schedule daily scrapes
   - Get alerts for rare opportunities
   - Track historical prices

3. **Scale Hardware**
   - Run scrapers in parallel
   - Distribute across multiple machines
   - Cache data to reduce API calls

4. **Analytics Dashboard**
   - Real-time opportunity feed
   - Profit tracking
   - Inventory management

## 💰 Expected Results

Based on typical MTG pricing:
- **Average margin**: 5-15%
- **Cards found per search**: 2-20
- **Daily profit potential**: $50-$500 (depends on volume)
- **Best opportunities**: Rare/foil cards, price differences between vendors

## 📖 Full Documentation

See `arbitrage-engine/README.md` for detailed technical documentation.

---

**Happy arbitraging! 🚀**

*Last Updated: March 2026*
