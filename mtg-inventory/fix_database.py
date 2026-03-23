#!/usr/bin/env python3
"""
Fix database issues:
1. Assign all cards to boxes
2. Fetch prices from Scryfall for all cards
"""
import os
import sys
import time
from pathlib import Path

# Add the mtg-inventory directory to the path
mtg_inv_dir = Path(__file__).parent
sys.path.insert(0, str(mtg_inv_dir))

from database import SessionLocal
from models import Card, Price
from services.location_engine import assign_location
from services.scryfall_api import ScryfallAPI

def assign_all_cards_to_boxes():
    """Assign all unassigned cards to boxes"""
    db = SessionLocal()
    
    try:
        # Find all cards without box assignments
        unassigned = db.query(Card).filter(Card.box_number.is_(None)).all()
        print(f"\n📦 Assigning {len(unassigned)} cards to boxes...")
        
        for i, card in enumerate(unassigned, 1):
            assign_location(db, card)
            if i % 10 == 0:
                db.flush()  # Periodically flush to update box counts
                print(f"  ✓ Assigned {i}/{len(unassigned)} cards")
        
        db.commit()
        print(f"✓ All cards assigned to boxes!")
        
        # Show box statistics
        from sqlalchemy import func
        box_stats = db.query(
            Card.box_number,
            func.count(Card.id).label('count')
        ).group_by(Card.box_number).all()
        
        print(f"\n📊 Box Distribution:")
        for box_num, count in box_stats:
            print(f"  - Box {box_num}: {count} cards")
        
    finally:
        db.close()


def fetch_prices_for_all_cards():
    """Fetch prices from Scryfall for all cards"""
    db = SessionLocal()
    
    try:
        cards = db.query(Card).all()
        print(f"\n💰 Fetching prices for {len(cards)} cards from Scryfall...")
        
        fetched = 0
        skipped = 0
        errors = 0
        
        for i, card in enumerate(cards, 1):
            if not card.scryfall_id or card.scryfall_id.startswith('invalid'):
                skipped += 1
                continue
            
            try:
                # Check if price already exists
                existing_price = db.query(Price).filter(
                    Price.scryfall_id == card.scryfall_id
                ).first()
                
                if existing_price:
                    skipped += 1
                    continue
                
                # Fetch from Scryfall
                scryfall_data = ScryfallAPI.get_card_by_id(card.scryfall_id)
                
                if scryfall_data and 'prices' in scryfall_data:
                    prices = scryfall_data['prices']
                    price_entry = Price(
                        scryfall_id=card.scryfall_id,
                        market_price=prices.get('usd'),
                        low_price=prices.get('usd_foil'),  # Not ideal, but better than nothing
                        high_price=prices.get('eur')
                    )
                    db.add(price_entry)
                    fetched += 1
                else:
                    skipped += 1
                
                # Rate limiting - be respectful to Scryfall API
                if i % 10 == 0:
                    db.flush()
                    print(f"  ✓ Fetched {fetched}/{len(cards)} prices ({skipped} skipped)")
                    time.sleep(0.1)  # 100ms delay between batches
                
            except Exception as e:
                errors += 1
                print(f"  ⚠ Error fetching price for {card.name}: {e}")
                continue
        
        db.commit()
        
        print(f"\n✓ Price fetch complete!")
        print(f"  - Fetched: {fetched}")
        print(f"  - Skipped: {skipped}")
        print(f"  - Errors: {errors}")
        
    finally:
        db.close()


def main():
    """Run all fixes"""
    print("=" * 70)
    print("DATABASE FIX: Assign Cards to Boxes & Fetch Prices")
    print("=" * 70)
    
    assign_all_cards_to_boxes()
    fetch_prices_for_all_cards()
    
    print("\n" + "=" * 70)
    print("✅ All fixes complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
