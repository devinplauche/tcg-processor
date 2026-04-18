#!/usr/bin/env python
"""
Quick validation test using the actual test.csv file
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, SessionLocal, Base
from sqlalchemy import create_engine
from services.manabox import import_csv
from models import Card, Box
import io

# Setup test database
engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(bind=engine)
from sqlalchemy.orm import sessionmaker
TestSession = sessionmaker(bind=engine)
db = TestSession()

# Read and import the test.csv (from parent directory)
with open('../test.csv', 'rb') as f:
    csv_data = f.read()

csv_file = io.BytesIO(csv_data)
try:
    result = import_csv(db, csv_file)
    print(f"✓ Import successful!")
    print(f"  Added: {result['added']}, Updated: {result['updated']}, Skipped: {result['skipped']}")
    
    # Verify cards were created
    cards = db.query(Card).all()
    print(f"✓ Cards in database: {len(cards)}")
    for card in cards:
        print(f"  - {card.name}: Box {card.box_number}, Slot {card.slot_number}")
        print(f"    Foil: {card.foil}, ManaBox ID: {card.manabox_id}")
    
    # Verify boxes were created
    boxes = db.query(Box).all()
    print(f"✓ Boxes in database: {len(boxes)}")
    for box in boxes:
        print(f"  - Box {box.box_number}: {box.current_count}/{box.capacity} cards")
        
except Exception as e:
    print(f"✗ Error during import: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
