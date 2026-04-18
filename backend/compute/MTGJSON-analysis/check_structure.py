import json

# Load the JSON file
with open('AllPricesToday.json', 'r') as f:
    data = json.load(f)

# Get metadata
print("Metadata:", data.get('meta'))
print()

# Get the actual data
card_data = data.get('data', {})
print(f"Total cards: {len(card_data)}")
print()

# Look at the first few cards with TCGPlayer prices
print("Sample cards with TCGPlayer retail prices:\n")
count = 0
for uuid, prices in card_data.items():
    if count >= 10:
        break
    
    if 'paper' in prices and 'tcgplayer' in prices['paper']:
        tcg_retail = prices['paper']['tcgplayer'].get('retail', {})
        if tcg_retail:
            print(f"UUID: {uuid[:8]}...")
            print(f"  TCGPlayer retail: {tcg_retail}")
            count += 1

# Check what data is actually present
print("\nChecking for high-value TCGPlayer items...")
high_values = []
for uuid, prices in card_data.items():
    if 'paper' in prices and 'tcgplayer' in prices['paper']:
        tcg_retail = prices['paper']['tcgplayer'].get('retail', {})
        for format_type, price_data in tcg_retail.items():
            if isinstance(price_data, dict):
                for date, price in price_data.items():
                    if isinstance(price, (int, float)) and price > 100:
                        high_values.append((uuid, format_type, price))

high_values.sort(key=lambda x: x[2], reverse=True)
print(f"\nFound {len(high_values)} TCGPlayer prices > $100")
if high_values:
    print("Top 10:")
    for uuid, fmt, price in high_values[:10]:
        print(f"  ${price} - {fmt}")
