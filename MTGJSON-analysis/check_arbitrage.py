import json

# Check for TCGPlayer prices in AllPricesToday.json
with open('AllPricesToday.json', 'r') as f:
    data = json.load(f)

prices_data = data.get('data', {})

# Sample a card and check all available price sources
sample_uuid = list(prices_data.keys())[0]
sample_card = prices_data[sample_uuid]

print("="*80)
print("Available Price Sources in AllPrices.json")
print("="*80)
print(f"\nSample card UUID: {sample_uuid}")
print(f"Card structure keys: {list(sample_card.keys())}")

# Check paper prices
if 'paper' in sample_card:
    paper = sample_card['paper']
    print(f"\nPaper price sources: {list(paper.keys())}")
    
    for source in paper.keys():
        source_data = paper[source]
        print(f"\n  {source}:")
        print(f"    Keys: {list(source_data.keys())}")
        
        if 'buylist' in source_data and source_data['buylist']:
            print(f"      Buylist: {list(source_data['buylist'].keys())}")
        if 'retail' in source_data and source_data['retail']:
            print(f"      Retail: {list(source_data['retail'].keys())}")

# Count cards with both CK buylist and TCGPlayer retail
print("\n" + "="*80)
print("Checking for Arbitrage Opportunities")
print("="*80)

ck_and_tcg = 0
ck_buylist_only = 0
tcg_retail_only = 0

for uuid, card in prices_data.items():
    paper = card.get('paper', {})
    
    ck_bl = paper.get('cardkingdom', {}).get('buylist', {}).get('normal', {})
    tcg_retail = paper.get('tcgplayer', {}).get('retail', {}).get('normal', {})
    
    ck_has = bool(ck_bl)
    tcg_has = bool(tcg_retail)
    
    if ck_has and tcg_has:
        ck_and_tcg += 1
    elif ck_has:
        ck_buylist_only += 1
    elif tcg_has:
        tcg_retail_only += 1

print(f"\nCards with BOTH CK buylist AND TCGPlayer retail: {ck_and_tcg:,}")
print(f"Cards with only CK buylist: {ck_buylist_only:,}")
print(f"Cards with only TCGPlayer retail: {tcg_retail_only:,}")

# Find potential arbitrage opportunities
print("\n" + "="*80)
print("Looking for Arbitrage: Retail < Card Kingdom Buylist (Half Payout)")
print("="*80)

arbitrage_opps = []
latest_date = max([d for card in prices_data.values() 
                   for d in card.get('paper', {}).get('cardkingdom', {}).get('buylist', {}).get('normal', {}).keys()])

print(f"Using latest date: {latest_date}")
print("Note: CK buylist values are halved to account for potential payment reduction\n")

for uuid, card in prices_data.items():
    paper = card.get('paper', {})
    
    ck_bl = paper.get('cardkingdom', {}).get('buylist', {}).get('normal', {})
    
    if not ck_bl:
        continue
    
    # Use latest date if available, otherwise use max available
    ck_price = None
    if latest_date in ck_bl:
        ck_price = float(ck_bl[latest_date]) * 0.5  # Half the payout
    else:
        ck_date = max([d for d in ck_bl.keys()])
        ck_price = float(ck_bl[ck_date]) * 0.5  # Half the payout
    
    # Collect all available retail prices from all sources
    retail_prices = {}
    for source, source_data in paper.items():
        if isinstance(source_data, dict) and 'retail' in source_data:
            retail = source_data.get('retail', {}).get('normal', {})
            if retail:
                price = None
                if latest_date in retail:
                    price = float(retail[latest_date])
                else:
                    retail_date = max([d for d in retail.keys()])
                    price = float(retail[retail_date])
                retail_prices[source] = price
    
    if not retail_prices:
        continue
    
    # Find minimum retail price across all sources
    min_retail_source = min(retail_prices, key=retail_prices.get)
    min_retail_price = retail_prices[min_retail_source]
    
    # Check for arbitrage (retail < halved CK buylist)
    if min_retail_price < ck_price:
        profit = ck_price - min_retail_price
        margin = (profit / min_retail_price) * 100 if min_retail_price > 0 else 0
        
        arbitrage_opps.append({
            'uuid': uuid,
            'ck_buylist_half': ck_price,
            'retail_source': min_retail_source,
            'retail_price': min_retail_price,
            'profit': profit,
            'margin': margin,
            'all_retail': retail_prices
        })

arbitrage_opps.sort(key=lambda x: x['profit'], reverse=True)

print(f"Found {len(arbitrage_opps)} arbitrage opportunities!")
print(f"\nTop 20 by profit:")
print(f"{'Profit':<10} {'Margin':<10} {'Retail Price':<14} {'CK Buylist (50%)':<16} {'Retail Source':<15}")
print("-" * 70)

for opp in arbitrage_opps[:20]:
    print(f"${opp['profit']:<9.2f} {opp['margin']:>7.1f}%  ${opp['retail_price']:<13.2f} ${opp['ck_buylist_half']:<15.2f} {opp['retail_source']:<15}")

if len(arbitrage_opps) > 20:
    print(f"... and {len(arbitrage_opps) - 20} more")
