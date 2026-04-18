import json
import gzip

# Load the JSON file
with open('AllPricesToday.json', 'r') as f:
    data = json.load(f)

# Load card identifiers
with gzip.open('allidentifiers_cache.json.gz', 'rt', encoding='utf-8') as f:
    identifiers_data = json.load(f)

# Create mapping from the data key
uuid_map = {}
for uuid, card_info in identifiers_data.get('data', {}).items():
    uuid_map[uuid] = card_info

# Get the actual data
card_data = data.get('data', {})

# Find highest TCGPlayer prices
high_values = []
for uuid, prices in card_data.items():
    if 'paper' in prices and 'tcgplayer' in prices['paper']:
        tcg_retail = prices['paper']['tcgplayer'].get('retail', {})
        for format_type, price_data in tcg_retail.items():
            if isinstance(price_data, dict):
                for date, price in price_data.items():
                    if price > 500:
                        high_values.append((uuid, format_type, price))

high_values.sort(key=lambda x: x[2], reverse=True)

print("Top 20 Most Expensive TCGPlayer Listings:\n")
for i, (uuid, fmt, price) in enumerate(high_values[:20], 1):
    card = uuid_map.get(uuid, {})
    name = card.get('name', 'Unknown')
    set_code = card.get('setCode', '')
    num = card.get('number', '')
    print(f"{i}. ${price:,.2f} - {name} {set_code} #{num} ({fmt})")
