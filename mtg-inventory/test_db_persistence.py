#!/usr/bin/env python3
"""
Test database persistence and ensure it's being used correctly
"""
import os
import sys
from pathlib import Path

# Add the mtg-inventory directory to the path
mtg_inv_dir = Path(__file__).parent
sys.path.insert(0, str(mtg_inv_dir))

from database import SessionLocal, DATABASE_URL
from models import Card, Box

def test_database_persistence():
    """Test that the database persists and is in the correct location"""
    
    print("=" * 70)
    print("DATABASE PERSISTENCE TEST")
    print("=" * 70)
    
    # Show database location
    print(f"\n📁 Database URL: {DATABASE_URL}")
    
    # Extract the actual file path
    db_path = DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
    print(f"📁 Database File: {db_path}")
    
    # Check if file exists
    if os.path.exists(db_path):
        file_size = os.path.getsize(db_path)
        print(f"✓ Database file exists ({file_size:,} bytes)")
    else:
        print(f"✗ Database file does not exist!")
        return False
    
    # Test database access
    print(f"\n🔍 Testing database access...")
    try:
        db = SessionLocal()
        
        # Count cards
        card_count = db.query(Card).count()
        print(f"✓ Card count: {card_count}")
        
        # Count boxes
        box_count = db.query(Box).count()
        print(f"✓ Box count: {box_count}")
        
        # List first few cards if any exist
        if card_count > 0:
            print(f"\n📋 First 5 cards in database:")
            cards = db.query(Card).limit(5).all()
            for i, card in enumerate(cards, 1):
                print(f"  {i}. {card.name} ({card.set_code}) - Qty: {card.quantity}")
        
        db.close()
        
    except Exception as e:
        print(f"✗ Error accessing database: {e}")
        return False
    
    print(f"\n✅ Database persistence test PASSED!")
    print(f"=" * 70)
    return True

if __name__ == "__main__":
    success = test_database_persistence()
    sys.exit(0 if success else 1)
