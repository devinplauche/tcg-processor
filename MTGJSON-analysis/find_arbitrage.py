#!/usr/bin/env python3
"""
Arbitrage Detector - Find cards where retail price < Card Kingdom buylist

Features:
- Checks all available retail sources (TCGPlayer, Manapool, etc.)
- Supports condition-based payouts (NM, EX, LP, VG, MP, G, HP)
- Default: 50% payout (conservative estimate for grading risk)
- Shows detailed card info with arbitrage opportunities
- Compare mode: view opportunities across all conditions
"""

import json
import gzip

CONFIG = {
    "min_profit": 5.00,  # Only show opportunities with at least $5 profit
    "default_payout": 0.50,  # Conservative 50% payout by default
    # Card Kingdom payout percentages by condition
    "conditions": {
        "NM": 1.00,      # Near Mint - 100%
        "EX": 0.80,      # Excellent - 80%
        "LP": 0.80,      # Light Play - 80%
        "VG": 0.70,      # Very Good - 70%
        "MP": 0.70,      # Moderate Play - 70%
        "G": 0.50,       # Good - 50%
        "HP": 0.50,      # Heavy Play - 50%
    }
}

def load_json_file(filepath):
    """Load JSON file, handling gzip if needed."""
    if filepath.endswith('.gz'):
        with gzip.open(filepath, 'rt', encoding='utf-8') as f:
            return json.load(f)
    else:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


def fetch_card_names():
    """Load card names from cached AllIdentifiers."""
    try:
        data = load_json_file("allidentifiers_cache.json.gz")
        if isinstance(data, dict) and 'data' in data:
            data = data['data']
        
        return {u: {
                    "name": v.get("name", "?"), 
                    "set": v.get("setCode", "?"),
                    "number": v.get("number", "?")
                }
                for u, v in data.items()}
    except Exception as e:
        print(f"Error loading identifiers: {e}")
        return {}


def compute_arbitrage(condition=None, min_profit=None):
    """Compute arbitrage opportunities and return structured results."""
    if min_profit is None:
        min_profit = CONFIG['min_profit']

    use_conditions = condition and condition != "COMPARE"
    payout_rate = CONFIG["conditions"].get(condition, CONFIG["default_payout"]) if use_conditions else CONFIG["default_payout"]

    card_names = fetch_card_names()
    with open('AllPricesToday.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    prices_data = data.get('data', {})

    latest_date = None
    for card in prices_data.values():
        paper = card.get('paper', {})
        ck_bl = paper.get('cardkingdom', {}).get('buylist', {}).get('normal', {})
        if ck_bl:
            latest_date = max(ck_bl.keys())
            break

    if not latest_date:
        return {
            'latest_date': None,
            'payout_rate': payout_rate,
            'opportunities': [],
            'summary': {
                'total_opportunities': 0,
                'total_profit': 0.0,
                'avg_profit': 0.0,
                'avg_margin': 0.0,
            },
        }

    arbitrage_opps = []

    for uuid, card in prices_data.items():
        paper = card.get('paper', {})
        ck_bl = paper.get('cardkingdom', {}).get('buylist', {}).get('normal', {})
        if not ck_bl:
            continue

        ck_price = float(ck_bl.get(latest_date, ck_bl[max(ck_bl.keys())]))
        ck_actual_payout = ck_price * payout_rate

        retail_prices = {}
        for source, source_data in paper.items():
            if isinstance(source_data, dict) and 'retail' in source_data:
                retail = source_data.get('retail', {}).get('normal', {})
                if retail:
                    price = float(retail.get(latest_date, retail[max(retail.keys())]))
                    retail_prices[source] = price

        if not retail_prices:
            continue

        min_retail_source = min(retail_prices, key=retail_prices.get)
        min_retail_price = retail_prices[min_retail_source]

        if min_retail_price < ck_actual_payout:
            profit = ck_actual_payout - min_retail_price
            margin = (profit / min_retail_price) * 100 if min_retail_price > 0 else 0

            if profit >= min_profit:
                info = card_names.get(uuid, {"name": "Unknown", "set": "?", "number": "?"})
                arbitrage_opps.append({
                    'uuid': uuid,
                    'name': info['name'],
                    'set': info['set'],
                    'number': info['number'],
                    'retail_source': min_retail_source,
                    'retail_price': min_retail_price,
                    'ck_listed': ck_price,
                    'ck_payout': ck_actual_payout,
                    'profit': profit,
                    'margin': margin,
                })

    arbitrage_opps.sort(key=lambda x: x['profit'], reverse=True)

    total_profit = sum(opp['profit'] for opp in arbitrage_opps)
    avg_profit = total_profit / len(arbitrage_opps) if arbitrage_opps else 0
    avg_margin = sum(opp['margin'] for opp in arbitrage_opps) / len(arbitrage_opps) if arbitrage_opps else 0

    return {
        'latest_date': latest_date,
        'payout_rate': payout_rate,
        'opportunities': arbitrage_opps,
        'summary': {
            'total_opportunities': len(arbitrage_opps),
            'total_profit': total_profit,
            'avg_profit': avg_profit,
            'avg_margin': avg_margin,
        },
    }


def main():
    import sys
    
    # Allow condition selection from command line
    condition = sys.argv[1].upper() if len(sys.argv) > 1 else None
    use_conditions = condition and condition != "COMPARE"
    
    if use_conditions and condition not in CONFIG["conditions"]:
        print(f"Usage: {sys.argv[0]} [NM|EX|LP|VG|MP|G|HP|compare]")
        print(f"Available conditions: {', '.join(CONFIG['conditions'].keys())}")
        sys.exit(1)
    
    if use_conditions:
        payout_rate = CONFIG["conditions"][condition]
        payout_label = f"{condition} Condition (CK Payout: {payout_rate*100:.0f}%)"
    else:
        payout_rate = CONFIG["default_payout"]
        payout_label = f"Conservative Estimate (CK Payout: {payout_rate*100:.0f}%)"
    
    print("=" * 130)
    print(f"Arbitrage Detector - Retail < Card Kingdom Buylist")
    print(f"{payout_label}")
    print("=" * 130)
    print(f"Min profit threshold: ${CONFIG['min_profit']:.2f}\n")
    
    print("[1] Loading and computing opportunities...")
    result = compute_arbitrage(condition=condition if use_conditions else None)
    latest_date = result['latest_date']
    arbitrage_opps = result['opportunities']

    print(f"    Using date: {latest_date}")
    
    print(f"    Found {len(arbitrage_opps)} opportunities >= ${CONFIG['min_profit']:.2f}\n")
    
    print("=" * 140)
    print(f"TOP 30 ARBITRAGE OPPORTUNITIES")
    print("=" * 140)
    print(f"{'Card Name':<35} {'Set':<6} {'#':<8} {'Retail Price':<14} {'CK Listed':<12} {'CK Payout':<12} {'Profit':<10} {'Source':<12} {'Margin':<10}")
    print("-" * 140)
    
    for i, opp in enumerate(arbitrage_opps[:30], 1):
        card_display = opp['name'][:34]
        num_display = str(opp['number'])[:7]
        print(f"{card_display:<35} {opp['set']:<6} {num_display:<8} ${opp['retail_price']:<13.2f} ${opp['ck_listed']:<11.2f} ${opp['ck_payout']:<11.2f} ${opp['profit']:<9.2f} {opp['retail_source']:<12} {opp['margin']:>7.1f}%")
    
    if len(arbitrage_opps) > 30:
        print(f"\n... and {len(arbitrage_opps) - 30} more opportunities!")
    
    # Summary statistics
    total_profit = result['summary']['total_profit']
    avg_profit = result['summary']['avg_profit']
    avg_margin = result['summary']['avg_margin']
    
    print("\n" + "=" * 140)
    print(f"SUMMARY STATISTICS")
    print("=" * 140)
    print(f"Total arbitrage opportunities: {len(arbitrage_opps):,}")
    print(f"Total potential profit (if executed all): ${total_profit:,.2f}")
    print(f"Average profit per card: ${avg_profit:.2f}")
    print(f"Average margin per card: {avg_margin:.1f}%")
    if arbitrage_opps:
        print(f"Highest profit opportunity: ${arbitrage_opps[0]['profit']:.2f} ({arbitrage_opps[0]['margin']:.1f}%)")
    print("=" * 140)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1].lower() == "compare":
        # Show all conditions side-by-side
        print("=" * 160)
        print("ARBITRAGE COMPARISON - ALL CONDITIONS")
        print("=" * 160)
        
        baseline = compute_arbitrage(condition=None)
        latest_date = baseline['latest_date']
        
        print(f"Date: {latest_date}\n")
        print(f"{'Condition':<12} {'Payout %':<12} {'Opportunities':<18} {'Total Profit':<16} {'Avg Profit':<16} {'Avg Margin':<12}")
        print("-" * 160)
        
        # First show default 50% conservative estimate
        payout_rate = CONFIG["default_payout"]
        total_profit = baseline['summary']['total_profit']
        avg_profit = baseline['summary']['avg_profit']
        avg_margin = baseline['summary']['avg_margin']
        print(f"{'Conservative':<12} {payout_rate*100:>9.0f}%   {baseline['summary']['total_opportunities']:>15,}   ${total_profit:>14,.2f}  ${avg_profit:>14.2f}  {avg_margin:>9.1f}%")
        
        # Then show all conditions
        for condition, payout_rate in CONFIG["conditions"].items():
            computed = compute_arbitrage(condition=condition)
            total_profit = computed['summary']['total_profit']
            avg_profit = computed['summary']['avg_profit']
            avg_margin = computed['summary']['avg_margin']

            print(f"{condition:<12} {payout_rate*100:>9.0f}%   {computed['summary']['total_opportunities']:>15,}   ${total_profit:>14,.2f}  ${avg_profit:>14.2f}  {avg_margin:>9.1f}%")
        
        print("=" * 160)
    else:
        main()
