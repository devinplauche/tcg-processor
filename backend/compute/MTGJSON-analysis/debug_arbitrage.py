import json

# Check for TCGPlayer prices in AllPrices.json
with open('AllPrices.json', 'r') as f:
    data = json.load(f)

prices_data = data.get('data', {})
print(f"Total cards: {len(prices_data)}")

# Sample a few cards to see structure
sample_uuids = list(prices_data.keys())[:5]
if not sample_uuids:
    print("No cards found in AllPrices.json data.")
    raise SystemExit(1)

for uuid in sample_uuids:
    card = prices_data[uuid]
    paper = card.get('paper', {})
    
    ck_bl = paper.get('cardkingdom', {}).get('buylist', {}).get('normal', {})
    tcg_retail = paper.get('tcgplayer', {}).get('retail', {}).get('normal', {})
    
    if ck_bl and tcg_retail:
        print(f"\nFound card with both: {uuid}")
        print(f"  CK Buylist: {list(ck_bl.items())[:2]}")
        print(f"  TCG Retail: {list(tcg_retail.items())[:2]}")
        break
else:
    print("\nNo cards found with both CK buylist and TCG retail in first 5")
    
    # Check what we do have
    sample_uuid = sample_uuids[0]
    card = prices_data[sample_uuid]
    paper = card.get('paper', {})
    print(f"\nSample card structure:")
    for source in paper.keys():
        source_data = paper[source]
        print(f"  {source}: {list(source_data.keys())}")
