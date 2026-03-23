import json

# Examine AllPrices.json structure
with open('AllPrices.json', 'r') as f:
    baseline = json.load(f)

print("=" * 80)
print("AllPrices.json Structure")
print("=" * 80)
if isinstance(baseline, dict) and 'data' in baseline:
    base_data = baseline['data']
    print(f"Type: dict with 'data' key")
    print(f"Total cards: {len(base_data):,}")
    
    # Sample a few cards to see the structure
    sample_uuids = list(base_data.keys())[:3]
    for uuid in sample_uuids:
        card = base_data[uuid]
        print(f"\nSample card UUID: {uuid}")
        print(f"  Keys: {list(card.keys())}")
        
        # Check for dates
        ck_bl = card.get('paper', {}).get('cardkingdom', {}).get('buylist', {}).get('normal', {})
        if ck_bl:
            print(f"  CK Buylist dates: {list(ck_bl.keys())}")
            for date_str, price in list(ck_bl.items())[:3]:
                print(f"    {date_str}: ${price}")
else:
    print(f"Type: {type(baseline)}")
    if isinstance(baseline, dict):
        print(f"Keys: {list(baseline.keys())}")

# Now check AllPricesToday.json
print("\n" + "=" * 80)
print("AllPricesToday.json Structure")
print("=" * 80)

with open('AllPricesToday.json', 'r') as f:
    today = json.load(f)

if isinstance(today, dict) and 'data' in today:
    meta = today.get('meta', {})
    print(f"Meta: {meta}")
    
    today_data = today['data']
    print(f"Total cards: {len(today_data):,}")
    
    # Sample a few cards
    sample_uuids = list(today_data.keys())[:3]
    for uuid in sample_uuids:
        card = today_data[uuid]
        ck_bl = card.get('paper', {}).get('cardkingdom', {}).get('buylist', {}).get('normal', {})
        if ck_bl:
            print(f"\nSample card UUID: {uuid}")
            print(f"  CK Buylist dates: {list(ck_bl.keys())}")
            for date_str, price in list(ck_bl.items())[:3]:
                print(f"    {date_str}: ${price}")

# Check dates across both datasets
print("\n" + "=" * 80)
print("Date Analysis")
print("=" * 80)

baseline_dates = set()
baseline_data = baseline.get('data', {})
for card in baseline_data.values():
    ck_bl = card.get('paper', {}).get('cardkingdom', {}).get('buylist', {}).get('normal', {})
    if ck_bl:
        baseline_dates.update(ck_bl.keys())

today_data = today.get('data', {})
today_dates = set()
for card in today_data.values():
    ck_bl = card.get('paper', {}).get('cardkingdom', {}).get('buylist', {}).get('normal', {})
    if ck_bl:
        today_dates.update(ck_bl.keys())

print(f"AllPrices.json dates: {sorted(baseline_dates)}")
print(f"AllPricesToday.json dates: {sorted(today_dates)}")
print(f"\nLatest in AllPrices: {max(baseline_dates) if baseline_dates else 'N/A'}")
print(f"Latest in AllPricesToday: {max(today_dates) if today_dates else 'N/A'}")
