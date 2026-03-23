#!/usr/bin/env python3
"""
Seed the database with legacy cards for testing
"""
import csv
import sys
import uuid
from database import SessionLocal, init_db
from models import Card, Box, SyncLog
from services.location_engine import assign_location

def seed_database():
    """Import legacy_cards.csv into the database"""
    init_db()
    db = SessionLocal()
    
    try:
        csv_file = 'legacy_cards.csv'
        
        # Read and import CSV
        added = 0
        updated = 0
        skipped = 0
        errors = 0
        seen_ids = {}
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    scryfall_id = row['scryfall_id'].strip()
                    
                    # Handle duplicates by creating unique IDs
                    if scryfall_id in seen_ids:
                        # Generate a unique ID for duplicate cards with different conditions/foils
                        scryfall_id = str(uuid.uuid4())
                    else:
                        seen_ids[scryfall_id] = True
                    
                    # Check if card already exists by name + condition + foil
                    name = row['name'].strip()
                    condition = row.get('condition', 'NM').strip()
                    foil = row.get('foil', '').lower() == 'foil'
                    
                    existing = db.query(Card).filter(
                        Card.name == name,
                        Card.condition == condition,
                        Card.foil == foil
                    ).first()
                    
                    if existing:
                        # Update existing card
                        existing.quantity = int(row.get('quantity', 1))
                        updated += 1
                    else:
                        # Create new card
                        card = Card(
                            scryfall_id=scryfall_id,
                            manabox_id=row.get('manabox_id', ''),
                            name=name,
                            set_code=row.get('set_code', ''),
                            collector_number=row.get('collector_number', ''),
                            foil=foil,
                            quantity=int(row.get('quantity', 1)),
                            condition=condition,
                            language=row.get('language', 'English'),
                            purchase_price=float(row.get('purchase_price', 0))
                        )
                        # Assign location to box
                        assign_location(db, card)
                        db.add(card)
                        added += 1
                
                except Exception as e:
                    print(f"⚠ Error processing {row.get('name', 'unknown')}: {e}")
                    errors += 1
                    continue
        
        # Log the sync
        sync_log = SyncLog(
            sync_type='csv_import',
            status='complete',
            cards_processed=added + updated,
            errors=errors
        )
        db.add(sync_log)
        
        db.commit()
        
        print(f"✓ Database seeded successfully!")
        print(f"  Added: {added}")
        print(f"  Updated: {updated}")
        print(f"  Errors: {errors}")
        
    except Exception as e:
        print(f"✗ Error seeding database: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == '__main__':
    seed_database()
