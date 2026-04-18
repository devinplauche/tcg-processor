#!/usr/bin/env python3
"""
MTG Arbitrage Engine
====================
Identifies profitable trading opportunities across different vendors.

The engine compares buy prices from source vendors (CardKingdom, Atomic Empire, TCGPlayer, eBay)
with sell prices from destination vendors to find arbitrage opportunities.

Architecture:
    - Loader: Ingest buylist CSVs from multiple sources
    - Analyzer: Find opportunities where buy_price + costs < sell_price
    - Reporter: Generate insights and recommendations

Usage:
    python arbitrage_engine.py --sources cardkingdom.csv atomic_empire.csv \
                               --destinations tcgplayer.csv ebay.csv
"""

import pandas as pd
import logging
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass
class Card:
    """Represents a Magic card with pricing across vendors."""
    name: str
    edition: str
    condition: str
    foil: bool
    
    def key(self) -> Tuple:
        """Unique identifier for a card."""
        return (self.name, self.edition, self.condition, self.foil)
    
    def __hash__(self):
        return hash(self.key())
    
    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.key() == other.key()


@dataclass
class VendorPrice:
    """Represents a price point from a specific vendor."""
    vendor: str
    price: float
    quantity_available: Optional[int] = None
    product_url: Optional[str] = None
    
    def __repr__(self):
        return f"{self.vendor}: ${self.price:.2f}"


@dataclass
class ArbitrageOpportunity:
    """Represents a profitable trading opportunity."""
    card: Card
    source_vendor: str
    source_price: float
    destination_vendor: str
    destination_price: float
    profit_per_unit: float
    profit_margin: float  # percentage
    quantity_available: int
    total_profit_potential: float
    
    def __repr__(self):
        return (
            f"{self.card.name} ({self.card.edition})\n"
            f"  Buy from {self.source_vendor} @ ${self.source_price:.2f}\n"
            f"  Sell to {self.destination_vendor} @ ${self.destination_price:.2f}\n"
            f"  Profit: ${self.profit_per_unit:.2f} per card ({self.profit_margin:.1f}%)\n"
            f"  Available: {self.quantity_available} cards\n"
            f"  Total profit potential: ${self.total_profit_potential:.2f}"
        )


# ── Data Loader ────────────────────────────────────────────────────────────

class BuylistLoader:
    """Loads and normalizes buylist CSV files from different vendors."""
    
    VENDOR_MAPPINGS = {
        "cardkingdom": {
            "name_col": "name",
            "edition_col": "edition",
            "condition_col": "condition",
            "foil_col": "foil",
            "price_col": "buy_price",
            "qty_col": "max_qty",
            "url_col": None,
        },
        "atomic_empire": {
            "name_col": "name",
            "edition_col": "edition",
            "condition_col": "condition",
            "foil_col": "foil",
            "price_col": "buy_price",
            "qty_col": "quantity_available",
            "url_col": "product_url",
        },
        "tcgplayer": {
            "name_col": "name",
            "edition_col": "set",
            "condition_col": "condition",
            "foil_col": "foil",
            "price_col": "price",
            "qty_col": "quantity",
            "url_col": "product_url",
        },
        "ebay": {
            "name_col": "title",
            "edition_col": "set",
            "condition_col": "condition",
            "foil_col": "foil",
            "price_col": "selling_price",
            "qty_col": None,
            "url_col": "item_url",
        },
    }
    
    @staticmethod
    def load_buylist(filepath: str, vendor: str) -> Dict[Card, VendorPrice]:
        """Load a buylist CSV and return card->price mapping."""
        vendor_lower = vendor.lower()
        
        if vendor_lower not in BuylistLoader.VENDOR_MAPPINGS:
            log.warning(f"Unknown vendor: {vendor}. Using default column mapping.")
            mapping = BuylistLoader.VENDOR_MAPPINGS["cardkingdom"]
        else:
            mapping = BuylistLoader.VENDOR_MAPPINGS[vendor_lower]
        
        try:
            df = pd.read_csv(filepath, keep_default_na=False)
            log.info(f"Loaded {len(df)} rows from {filepath}")
        except FileNotFoundError:
            log.error(f"File not found: {filepath}")
            return {}
        except Exception as e:
            log.error(f"Error reading {filepath}: {e}")
            return {}
        
        card_prices: Dict[Card, VendorPrice] = {}
        
        for idx, row in df.iterrows():
            try:
                # Extract card info
                name = row.get(mapping["name_col"], "").strip()
                edition = str(row.get(mapping["edition_col"], "Unknown")).strip()
                condition = str(row.get(mapping["condition_col"], "NM")).strip()
                foil = BuylistLoader._parse_bool(row.get(mapping["foil_col"], False))
                price = BuylistLoader._parse_price(row.get(mapping["price_col"], 0))
                qty_str = row.get(mapping["qty_col"], "1")
                qty = BuylistLoader._parse_quantity(qty_str)
                
                # Optional fields
                url = None
                if mapping["url_col"] and mapping["url_col"] in row:
                    url = row.get(mapping["url_col"])
                
                if not name or price <= 0:
                    continue
                
                card = Card(
                    name=name,
                    edition=edition,
                    condition=condition,
                    foil=foil,
                )
                
                vendor_price = VendorPrice(
                    vendor=vendor,
                    price=price,
                    quantity_available=qty,
                    product_url=url,
                )
                
                card_prices[card] = vendor_price
            
            except Exception as e:
                log.debug(f"Error parsing row {idx}: {e}")
                continue
        
        log.info(f"Extracted {len(card_prices)} unique cards from {vendor}")
        return card_prices
    
    @staticmethod
    def _parse_bool(value) -> bool:
        """Parse boolean value from various formats."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "foil")
        return False
    
    @staticmethod
    def _parse_price(value) -> float:
        """Parse price from various formats."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace("$", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0
    
    @staticmethod
    def _parse_quantity(value) -> int:
        """Parse quantity from various formats."""
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            if value.lower() in ("n/a", "unknown", ""):
                return 1
            try:
                return int(value)
            except ValueError:
                return 1
        return 1


# ── Arbitrage Analyzer ──────────────────────────────────────────────────────

class ArbitrageAnalyzer:
    """Analyzes buylist data to find arbitrage opportunities."""
    
    # Assumed costs for each vendor (shipping, fees, storage, etc.)
    VENDOR_COSTS = {
        "cardkingdom": 0.50,      # Shipping + handling
        "atomic_empire": 2.00,    # Local pickup/shipping
        "tcgplayer": 0.75,        # Seller fees + packaging
        "ebay": 2.50,             # eBay/PayPal fees + shipping
    }
    
    MINIMUM_PROFIT = 0.50  # Minimum profit per card to consider
    MINIMUM_MARGIN = 0.10  # Minimum 10% margin
    
    def __init__(self):
        self.cards_by_name: Dict[str, Dict[Tuple, Tuple[Card, VendorPrice]]] = {}
        self.all_opportunities: List[ArbitrageOpportunity] = []
    
    def add_vendor_data(self, cards: Dict[Card, VendorPrice]) -> None:
        """Add card prices from a vendor to the analyzer."""
        for card, vendor_price in cards.items():
            if card.name not in self.cards_by_name:
                self.cards_by_name[card.name] = {}
            
            # Store by (edition, condition, foil, vendor) to avoid duplicates
            vendor_key = (card.edition, card.condition, card.foil, vendor_price.vendor)
            self.cards_by_name[card.name][vendor_key] = (card, vendor_price)
    
    def find_opportunities(self, min_profit: float = None, min_margin: float = None) -> List[ArbitrageOpportunity]:
        """Find all arbitrage opportunities."""
        if min_profit is None:
            min_profit = self.MINIMUM_PROFIT
        if min_margin is None:
            min_margin = self.MINIMUM_MARGIN
        
        opportunities: List[ArbitrageOpportunity] = []
        
        for card_name, card_dict in self.cards_by_name.items():
            # Get all (card, price) tuples for this card name
            card_entries = list(card_dict.values())
            
            # For each vendor pair, find arbitrage
            for source_card, source_price in card_entries:
                for dest_card, dest_price in card_entries:
                    # Skip same vendor
                    if source_price.vendor == dest_price.vendor:
                        continue
                    
                    # Skip if cards don't match (different edition/condition)
                    if source_card != dest_card:
                        continue
                    
                    # Calculate profit
                    source_cost = self.VENDOR_COSTS.get(source_price.vendor.lower(), 1.00)
                    profit_per_unit = dest_price.price - source_price.price - source_cost
                    
                    if profit_per_unit < min_profit:
                        continue
                    
                    # Calculate margin
                    margin = (profit_per_unit / source_price.price) if source_price.price > 0 else 0
                    if margin < min_margin:
                        continue
                    
                    qty = source_price.quantity_available or 1
                    total_profit = profit_per_unit * qty
                    
                    opportunity = ArbitrageOpportunity(
                        card=source_card,
                        source_vendor=source_price.vendor,
                        source_price=source_price.price,
                        destination_vendor=dest_price.vendor,
                        destination_price=dest_price.price,
                        profit_per_unit=profit_per_unit,
                        profit_margin=margin * 100,  # Convert to percentage
                        quantity_available=qty,
                        total_profit_potential=total_profit,
                    )
                    
                    opportunities.append(opportunity)
        
        self.all_opportunities = opportunities
        return opportunities
    
    def get_top_opportunities(self, limit: int = 20, sort_by: str = "profit") -> List[ArbitrageOpportunity]:
        """Get top opportunities sorted by profit or margin."""
        if sort_by == "margin":
            sorted_opps = sorted(
                self.all_opportunities,
                key=lambda x: x.profit_margin,
                reverse=True
            )
        else:  # Default to profit
            sorted_opps = sorted(
                self.all_opportunities,
                key=lambda x: x.total_profit_potential,
                reverse=True
            )
        
        return sorted_opps[:limit]


# ── Reporting ──────────────────────────────────────────────────────────────

class ArbitrageReporter:
    """Generates reports and insights from arbitrage analysis."""
    
    @staticmethod
    def print_summary(analyzer: ArbitrageAnalyzer) -> None:
        """Print summary statistics."""
        opps = analyzer.all_opportunities
        
        if not opps:
            print("No arbitrage opportunities found.")
            return
        
        total_profit = sum(o.total_profit_potential for o in opps)
        total_cards = sum(o.quantity_available for o in opps)
        avg_margin = sum(o.profit_margin for o in opps) / len(opps) if opps else 0
        
        print(f"\n{'='*80}")
        print(f"  ARBITRAGE ANALYSIS SUMMARY")
        print(f"{'='*80}")
        print(f"Total Opportunities Found: {len(opps)}")
        print(f"Total Cards Available: {total_cards}")
        print(f"Total Profit Potential: ${total_profit:.2f}")
        print(f"Average Profit Margin: {avg_margin:.1f}%")
        print()
    
    @staticmethod
    def print_top_opportunities(analyzer: ArbitrageAnalyzer, limit: int = 20) -> None:
        """Print top opportunities."""
        opportunities = analyzer.get_top_opportunities(limit=limit)
        
        if not opportunities:
            print("No opportunities found.")
            return
        
        print(f"\n{'='*80}")
        print(f"  TOP {len(opportunities)} ARBITRAGE OPPORTUNITIES (by profit potential)")
        print(f"{'='*80}\n")
        
        for i, opp in enumerate(opportunities, 1):
            print(f"{i}. {opp}")
            print()
    
    @staticmethod
    def save_opportunities_csv(
        opportunities: List[ArbitrageOpportunity],
        filepath: str
    ) -> None:
        """Save opportunities to CSV for further analysis."""
        data = []
        for opp in opportunities:
            data.append({
                "card_name": opp.card.name,
                "edition": opp.card.edition,
                "condition": opp.card.condition,
                "foil": opp.card.foil,
                "source_vendor": opp.source_vendor,
                "buy_price": f"${opp.source_price:.2f}",
                "destination_vendor": opp.destination_vendor,
                "sell_price": f"${opp.destination_price:.2f}",
                "profit_per_unit": f"${opp.profit_per_unit:.2f}",
                "profit_margin": f"{opp.profit_margin:.1f}%",
                "quantity_available": opp.quantity_available,
                "total_profit_potential": f"${opp.total_profit_potential:.2f}",
            })
        
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False)
        log.info(f"Saved {len(data)} opportunities to {filepath}")
    
    @staticmethod
    def save_opportunities_json(
        opportunities: List[ArbitrageOpportunity],
        filepath: str
    ) -> None:
        """Save opportunities to JSON for API consumption."""
        data = []
        for opp in opportunities:
            data.append({
                "card": {
                    "name": opp.card.name,
                    "edition": opp.card.edition,
                    "condition": opp.card.condition,
                    "foil": opp.card.foil,
                },
                "source": {
                    "vendor": opp.source_vendor,
                    "price": round(opp.source_price, 2),
                },
                "destination": {
                    "vendor": opp.destination_vendor,
                    "price": round(opp.destination_price, 2),
                },
                "profit": {
                    "per_unit": round(opp.profit_per_unit, 2),
                    "margin_percent": round(opp.profit_margin, 1),
                },
                "quantity_available": opp.quantity_available,
                "total_profit_potential": round(opp.total_profit_potential, 2),
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log.info(f"Saved {len(data)} opportunities to {filepath}")


# ── CLI ────────────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Find MTG arbitrage opportunities across vendors.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--sources", nargs="+", required=True,
        help="CSV files to use as buy sources (e.g., cardkingdom.csv atomic_empire.csv)"
    )
    p.add_argument(
        "--destinations", nargs="+",
        help="CSV files to use as sell destinations (default: same as sources)"
    )
    p.add_argument(
        "--output", "-o", default="arbitrage_opportunities.csv",
        help="Output CSV file for opportunities (default: arbitrage_opportunities.csv)"
    )
    p.add_argument(
        "--json-output",
        help="Also save opportunities to JSON format"
    )
    p.add_argument(
        "--min-profit", type=float, default=0.50,
        help="Minimum profit per card to report (default: $0.50)"
    )
    p.add_argument(
        "--min-margin", type=float, default=0.10,
        help="Minimum profit margin percentage (default: 10%%)"
    )
    p.add_argument(
        "--limit", type=int, default=20,
        help="Number of top opportunities to display (default: 20)"
    )
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging"
    )
    return p


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Use same files as sources and destinations if not specified
    destinations = args.destinations or args.sources
    
    # Initialize analyzer
    analyzer = ArbitrageAnalyzer()
    
    log.info("Loading buylist data...")
    
    # Load source (buy) data
    for filepath in args.sources:
        # Detect vendor from filename
        vendor_key = Path(filepath).stem.replace("_buylist", "").replace(" ", "_").lower()
        vendor_display = vendor_key.replace("_", " ").title()
        log.info(f"Loading source from {filepath} (vendor: {vendor_display})")
        cards = BuylistLoader.load_buylist(filepath, vendor_key)
        analyzer.add_vendor_data(cards)
    
    # Load destination (sell) data
    for filepath in destinations:
        vendor_key = Path(filepath).stem.replace("_buylist", "").replace(" ", "_").lower()
        vendor_display = vendor_key.replace("_", " ").title()
        log.info(f"Loading destination from {filepath} (vendor: {vendor_display})")
        cards = BuylistLoader.load_buylist(filepath, vendor_key)
        analyzer.add_vendor_data(cards)
    
    log.info("Analyzing for arbitrage opportunities...")
    
    # Find opportunities
    opportunities = analyzer.find_opportunities(
        min_profit=args.min_profit,
        min_margin=args.min_margin
    )
    
    # Print results
    ArbitrageReporter.print_summary(analyzer)
    ArbitrageReporter.print_top_opportunities(analyzer, limit=args.limit)
    
    # Save results
    ArbitrageReporter.save_opportunities_csv(opportunities, args.output)
    
    if args.json_output:
        ArbitrageReporter.save_opportunities_json(opportunities, args.json_output)
    
    log.info("Done!")


if __name__ == "__main__":
    main()
