#!/usr/bin/env python
"""
Test Data Initialization Script

Creates a persistent test database with realistic MTG card data.
Run this ONCE to generate data, then all tests use the saved data.

Usage:
    python setup_test_data.py                    # Creates test_data.db
    python setup_test_data.py --db-path custom.db    # Custom location
    python setup_test_data.py --count 10000           # Generate 10k cards
    python setup_test_data.py --reset                 # Delete & recreate
"""

import os
import sys
import argparse
import sqlite3
from pathlib import Path

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from models import Card, Box, Price
from services.data_generator import DataGenerator


def setup_test_database(db_path: str = "test_data.db", card_count: int = 5000, reset: bool = False):
    """
    Set up a persistent test database with realistic data.
    
    Args:
        db_path: Path to database file
        card_count: Number of cards to generate
        reset: If True, delete and recreate the database
    """
    db_file = Path(db_path)
    
    # Handle reset
    if reset and db_file.exists():
        print(f"🗑️  Removing existing database: {db_path}")
        db_file.unlink()
    
    is_new = not db_file.exists()
    
    # Create database connection
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    
    print(f"📦 Setting up database: {db_path}")
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database schema created")
    
    # Check if data already exists
    Session = sessionmaker(bind=engine)
    session = Session()
    
    existing_count = session.query(Card).count()
    
    if existing_count > 0 and not reset:
        print(f"\n✅ Database already has {existing_count} cards!")
        print("   To regenerate, use: python setup_test_data.py --reset")
        session.close()
        return existing_count
    
    # Generate test data
    print(f"\n🔄 Generating {card_count:,} test cards...")
    print("   (This may take a minute or two)")
    
    generator = DataGenerator(session)
    generated = generator.generate(count=card_count, batch_size=500)
    
    print(f"\n✅ Generated {generated:,} cards!")
    
    # Verify
    count = session.query(Card).count()
    print(f"✅ Database verified: {count:,} cards in database")
    
    # Print sample data
    sample_cards = session.query(Card).limit(3).all()
    print("\n📋 Sample cards:")
    for card in sample_cards:
        print(f"   - {card.name} ({card.set_code}) - ${card.purchase_price}")
    
    session.close()
    
    return generated


def print_database_stats(db_path: str = "test_data.db"):
    """Print statistics about the test database."""
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    session = Session()
    
    card_count = session.query(Card).count()
    box_count = session.query(Box).count()
    price_count = session.query(Price).count()
    
    print(f"\n📊 Database Statistics: {db_path}")
    print(f"   Cards: {card_count:,}")
    print(f"   Boxes: {box_count:,}")
    print(f"   Prices: {price_count:,}")
    
    if card_count > 0:
        # Stats
        foil_count = session.query(Card).filter(Card.foil == True).count()
        avg_price = session.query(Card).with_entities(
            session.query(Card.purchase_price).scalar()
        ).count() if card_count > 0 else 0
        
        print(f"\n   Foil cards: {foil_count:,} ({100*foil_count/card_count:.1f}%)")
        
        # Sample set distribution
        from sqlalchemy import func
        set_dist = session.query(
            Card.set_code,
            func.count(Card.id).label('count')
        ).group_by(Card.set_code).order_by(func.count(Card.id).desc()).limit(5).all()
        
        print(f"\n   Top sets:")
        for set_code, count in set_dist:
            print(f"      {set_code}: {count}")
    
    session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Initialize persistent test database with MTG card data"
    )
    parser.add_argument(
        '--db-path',
        default='test_data.db',
        help='Path to database file (default: test_data.db)'
    )
    parser.add_argument(
        '--count',
        type=int,
        default=5000,
        help='Number of cards to generate (default: 5000)'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Delete and recreate database'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show database statistics'
    )
    
    args = parser.parse_args()
    
    if args.stats:
        print_database_stats(args.db_path)
        return
    
    generated = setup_test_database(
        db_path=args.db_path,
        card_count=args.count,
        reset=args.reset
    )
    
    print("\n" + "="*60)
    print("✅ TEST DATA INITIALIZATION COMPLETE!")
    print("="*60)
    print(f"\n📊 Generated: {generated:,} cards")
    print(f"📁 Location: {os.path.abspath(args.db_path)}")
    print(f"\n💡 Now you can run tests:")
    print(f"   pytest test_chaos_sort.py -v")
    print(f"   pytest tests/integration/ --integration -v")
    print(f"\n🔄 To regenerate data:")
    print(f"   python setup_test_data.py --reset")
    print()


if __name__ == '__main__':
    main()
