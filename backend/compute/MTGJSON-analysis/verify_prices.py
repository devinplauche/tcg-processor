import json
import gzip

# Load the JSON file
with open('AllPricesToday.json', 'r') as f:
    data = json.load(f)

# Load card names
with gzip.open('allidentifiers_cache.json.gz', 'rt') as f:
    identifiers = json.load(f)

# Create UUID to name mapping
uuid_to_name = {}
for card in identifiers:
    uuid_to_name[card.get('uuid')] = f"{card.get('name')} {card.get('setCode', '')} #{card.get('number', '')}"

# Look for some high-value cards
high_value_cards = []
for uuid, prices in data.items():
    if uuid not in uuid_to_name:
        continue
    
    name = uuid_to_name[uuid]
    
    # Check TCGPlayer retail
    if 'paper' in prices and 'tcgplayer' in prices['paper']:
        tcg_retail = prices['paper']['tcgplayer'].get('retail', {})
        if tcg_retail:
            # Get the price (should be nested by format)
            for format_key, format_prices in tcg_retail.items():
                if isinstance(format_prices, dict):
                    for date, price in format_prices.items():
                        if isinstance(price, (int, float)) and price > 20:
                            high_value_cards.append({
                                'name': name,
                                'tcg_price': price,
                                'date': date
                            })

# Sort and show top 20
high_value_cards.sort(key=lambda x: x['tcg_price'], reverse=True)
print('Top 20 Most Expensive TCGPlayer Prices in AllPricesToday.json:')
print()
for item in high_value_cards[:20]:
    print(f"{item['name']}: ${item['tcg_price']} (as of {item['date']})")

print("\n\nDebug: First TCGPlayer entry structure:")
for uuid, prices in list(data.items())[:50]:
    if uuid not in uuid_to_name:
        continue
    if 'paper' in prices and 'tcgplayer' in prices['paper']:
        print(f"\n{uuid_to_name[uuid]}:")
        print(f"  TCGPlayer data: {prices['paper']['tcgplayer']}")
        break
