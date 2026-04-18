import json
import gzip

# Load AllPricesToday to check structure
with open('AllPricesToday.json', 'r') as f:
    today = json.load(f)

data = today.get('data', {})

# Load identifiers to see what info is available
with gzip.open('allidentifiers_cache.json.gz', 'rt', encoding='utf-8') as f:
    identifiers = json.load(f).get('data', {})

# Find all Psychic Frog entries
psychic_frogs = {}
for uuid, info in identifiers.items():
    if 'Psychic Frog' in info.get('name', ''):
        psychic_frogs[uuid] = info

print(f"Found {len(psychic_frogs)} Psychic Frog printings")
print("\nPsychic Frog variants:")
for uuid, info in psychic_frogs.items():
    set_code = info.get('setCode', '?')
    collector_num = info.get('number', 'N/A')
    print(f"  UUID: {uuid}")
    print(f"    Set: {set_code}, Name: {info.get('name')}")
    print(f"    Collector#: {collector_num}")
    if uuid in data:
        ck_bl = data[uuid].get('paper', {}).get('cardkingdom', {}).get('buylist', {}).get('normal', {})
        if ck_bl:
            latest_date = max(ck_bl.keys())
            price = ck_bl[latest_date]
            print(f"    CK Buylist: ${price}")
        else:
            print(f"    CK Buylist: (no price data)")
    else:
        print(f"    CK Buylist: (no price data)")
    print()
