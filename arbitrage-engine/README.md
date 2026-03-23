# MTG Arbitrage Engine - Setup & Usage Guide

## Overview

The MTG Arbitrage Engine is a sophisticated system for finding profitable card trading opportunities across different Magic: The Gathering vendors. It compares buy and sell prices to identify cards where you can purchase low from one vendor and sell high to another.

## Architecture

```
buylist-updater/
├── cardkingdom_scraper_selenium.py      # Scrapes CardKingdom buylist
├── atomic_empire_scraper.py             # Scrapes Atomic Empire buylist (NEW)
└── requirements.txt                      # Dependencies

arbitrage-engine/
├── arbitrage_engine.py                  # Core arbitrage analysis engine (NEW)
└── README.md                            # This file
```

## Features

### Scrapers
- **CardKingdom Scraper**: Fetches buylist prices from CardKingdom
- **Atomic Empire Scraper**: Fetches inventory/buylist prices from Atomic Empire (preferred local store)
- **Extensible Design**: Easy to add TCGPlayer, eBay, and other vendors

### Arbitrage Engine
- **Price Comparison**: Cross-vendor price analysis
- **Opportunity Detection**: Identifies profitable buy/sell combinations
- **Profit Calculation**: Accounts for vendor costs (shipping, fees, etc.)
- **Margin Analysis**: Filters opportunities by minimum profit margin
- **Multi-format Output**: CSV and JSON reports

## Installation

### 1. Install System Dependencies

**Windows:**
```powershell
# Install ChromeDriver matching your Chrome version
# Download from: https://chromedriver.chromium.org/
# Place in PATH or specify location in scraper
```

**macOS:**
```bash
brew install chromedriver
```

**Linux:**
```bash
# Debian/Ubuntu
sudo apt-get install chromium-chromedriver
```

### 2. Install Python Dependencies

```bash
cd tcg-processor
pip install -r buylist-updater/requirements.txt
```

## Usage Guide

### Step 1: Scrape Buylist Data

#### Scrape a Single Card from Atomic Empire
```bash
cd buylist-updater
python atomic_empire_scraper.py --search "Black Lotus" --output atomic_empire_buylist.csv
```

#### Bulk Scrape Multiple Cards
Create a file `cards.txt` with one card per line:
```
Black Lotus
Lightning Bolt
Path to Exile
```

Then run:
```bash
python atomic_empire_scraper.py --bulk-file cards.txt --output atomic_empire_buylist.csv
```

#### Scrape CardKingdom (Existing)
```bash
python cardkingdom_scraper_selenium.py --search "Black Lotus" --output cardkingdom_buylist.csv
```

### Step 2: Run Arbitrage Analysis

Once you have CSV files from multiple vendors:

```bash
cd ..
python arbitrage-engine/arbitrage_engine.py \
  --sources buylist-updater/atomic_empire_buylist.csv buylist-updater/cardkingdom_buylist.csv \
  --destinations buylist-updater/tcgplayer_buylist.csv \
  --output arbitrage_opportunities.csv \
  --min-profit 0.50 \
  --min-margin 0.10
```

**Parameters:**
- `--sources`: Vendorfiles to buy from (can use same files as destinations for cross-vendor comparison)
- `--destinations`: Vendor files to sell to (optional, defaults to sources)
- `--output`: Where to save the CSV report (default: arbitrage_opportunities.csv)
- `--json-output`: Also save results as JSON for API consumption
- `--min-profit`: Minimum profit per card in dollars (default: $0.50)
- `--min-margin`: Minimum profit margin percentage (default: 10%)
- `--limit`: Number of top opportunities to display (default: 20)
- `--verbose`: Enable debug logging

## Example Workflow

### Complete End-to-End Example

```bash
# 1. Get Atomic Empire prices for specific cards
cd buylist-updater
python atomic_empire_scraper.py \
  --bulk-file ../docs/high_value_cards.txt \
  --output atomic_empire_buylist.csv \
  --verbose

# 2. Get CardKingdom prices
python cardkingdom_scraper_selenium.py \
  --search "Tarmagoyf" \
  --output cardkingdom_buylist.csv

# 3. Run arbitrage analysis
cd ../arbitrage-engine
python arbitrage_engine.py \
  --sources ../buylist-updater/atomic_empire_buylist.csv \
  --destinations ../buylist-updater/cardkingdom_buylist.csv \
  --output opportunities.csv \
  --json-output opportunities.json \
  --min-profit 1.00 \
  --min-margin 0.15 \
  --limit 30

# 4. Review results
cat opportunities.csv
```

## Output Format

### CSV Output (arbitrage_opportunities.csv)
```
card_name,edition,condition,foil,source_vendor,buy_price,destination_vendor,sell_price,profit_per_unit,profit_margin,quantity_available,total_profit_potential
Black Lotus,Alpha,NM,False,Atomic Empire,$1500.00,TCGPlayer,$1600.00,$50.00,3.3%,1,$50.00
```

### JSON Output (opportunities.json)
```json
[
  {
    "card": {
      "name": "Black Lotus",
      "edition": "Alpha",
      "condition": "NM",
      "foil": false
    },
    "source": {
      "vendor": "Atomic Empire",
      "price": 1500.00
    },
    "destination": {
      "vendor": "TCGPlayer",
      "price": 1600.00
    },
    "profit": {
      "per_unit": 50.00,
      "margin_percent": 3.3
    },
    "quantity_available": 1,
    "total_profit_potential": 50.00
  }
]
```

## Vendor Configuration

The engine includes vendor-specific mappings for CSV column names. Supported vendors:

| Vendor | Mapping | Notes |
|--------|---------|-------|
| CardKingdom | Standard | name, edition, condition, foil, buy_price, max_qty |
| Atomic Empire | Standard | name, edition, condition, foil, buy_price, quantity_available, product_url |
| TCGPlayer | Custom | Expects: name, set, condition, foil, price |
| eBay | Custom | Expects: title, set, condition, foil, selling_price |

To add a new vendor, update `VENDOR_MAPPINGS` in `arbitrage_engine.py`.

## Vendor Costs

The engine accounts for vendor-specific transaction costs:

```python
VENDOR_COSTS = {
    "cardkingdom": 0.50,      # Shipping + handling
    "atomic_empire": 2.00,    # Local pickup/shipping
    "tcgplayer": 0.75,        # Seller fees + packaging
    "ebay": 2.50,             # eBay/PayPal fees + shipping
}
```

Adjust these values in `arbitrage_engine.py` based on your actual costs.

## Tips for Maximizing Results

1. **Local Preference**: Atomic Empire offers no shipping fees for local pickup, making it ideal for sourcing
2. **Condition Matters**: NM (Near Mint) cards command higher prices; cheaper LP or MP cards may offer better margins
3. **Foil Premium**: Foil versions often have higher margins due to lower supply
4. **Volume Strategy**: Target cards with high quantity available for bulk opportunities
5. **Timing**: Price differences fluctuate; run analysis regularly to catch trends
6. **Niche Sets**: Older sets often have better margins; focus on Alpha, Beta, and Arabian Nights

## Troubleshooting

### ChromeDriver Issues
```
Failed to create Chrome driver: [Errno 2] No such file or directory
```
Solution: Install ChromeDriver matching your Chrome version and add to PATH

### Empty Results
- Check card names - exact spelling matters
- Verify website URLs haven't changed
- Try with `--no-headless` to see browser interactions
- Enable `--verbose` logging

### Timeout Errors
- Increase timeout in scraper code (default: 10 seconds)
- Check network connection
- Some vendors may rate-limit; add delays with `time.sleep()`

### Price Parsing Issues
- Enable verbose logging to see what prices were extracted
- Check CSV column names match vendor mapping
- Some vendors use different decimal separators (. vs ,)

## API Integration (Future)

The engine is designed to integrate with external APIs:

```python
# Example: Pull live prices from APIs instead of CSV
from services.scryfall_api import ScryfallAPI
from services.tcgplayer_api import TCGPlayerAPI

prices = TCGPlayerAPI.get_prices(card_name)
```

See `/mtg-inventory/services/` for existing API implementations.

## Performance Notes

- Scraping: ~5-10 seconds per card (depends on site responsiveness)
- Analysis: <1 second for 1000 unique cards
- Storage: ~50 KB per 100 cards in CSV format

For bulk scraping, consider:
- Running overnight batches
- Distributing across multiple machines
- Implementing caching to avoid re-scraping

## Future Enhancements

- [ ] TCGPlayer scraper
- [ ] eBay scraper
- [ ] Real-time price monitoring with alerts
- [ ] Database storage instead of CSV
- [ ] REST API for opportunity queries
- [ ] Web dashboard for visualizing opportunities
- [ ] Automated trading bot integration
- [ ] Historical price tracking for trend analysis

## Contact & Contributing

For issues, improvements, or new vendor integrations, see the main project README.

Last Updated: March 2026
