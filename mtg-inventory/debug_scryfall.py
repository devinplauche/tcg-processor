#!/usr/bin/env python3
"""Debug price fetching"""
import sys
from pathlib import Path

mtg_inv_dir = Path(__file__).parent
sys.path.insert(0, str(mtg_inv_dir))

from database import SessionLocal
from models import Card
from services.scryfall_api import ScryfallAPI

db = SessionLocal()

# Get a few cards with real scryfall IDs
cards = db.query(Card).filter(~Card.scryfall_id.like('%-%-%-%')).limit(3).all()
print('Sample cards and Scryfall lookup:')

for card in cards:
    print(f'\n  Card: {card.name} (ID: {card.scryfall_id})')
    if card.scryfall_id:
        data = ScryfallAPI.get_card_by_id(card.scryfall_id)
        if data:
            print(f'    ✓ Found on Scryfall')
            prices = data.get('prices', {})
            print(f'    Prices: {prices}')
        else:
            print(f'    ✗ NOT found on Scryfall')

# Check for invalid IDs
invalid = db.query(Card).filter(Card.scryfall_id.like('%-%-%-%')).count()
valid = db.query(Card).filter(~Card.scryfall_id.like('%-%-%-%')).count()
print(f'\n📊 Scryfall ID Summary:')
print(f'  - Valid IDs: {valid}')
print(f'  - Invalid UUIDs (duplicates): {invalid}')

db.close()
