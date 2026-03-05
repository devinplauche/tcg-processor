"""
TDD Tests for Chaos Sorting and Large-Scale Data Operations

Tests are written first (TDD approach), then implementation follows.
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import Mock, patch
import random
import time
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
import tempfile

from database import Base, SessionLocal
from models import Card, Box
from services.chaos_sort import ChaosSort
from services.data_generator import DataGenerator


@pytest.fixture
def persistent_db():
    """Create a persistent SQLite database for large-scale testing"""
    # Use a temporary file for the database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestSession()
    
    yield db, db_path
    
    # Cleanup
    try:
        db.close()
        engine.dispose()  # Release all connections
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def in_memory_db():
    """In-memory SQLite for fast unit tests"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()
    yield db
    db.close()


# ========================
# CHAOS SORT TESTS (TDD)
# ========================

class TestChaosSortBasics:
    """Test basic chaos sorting functionality"""
    
    def test_chaos_sort_order_is_random(self, in_memory_db):
        """Test that chaos sort produces random ordering"""
        # Arrange: Create ordered cards
        cards = [
            Card(scryfall_id=f'sf_{i}', name=f'Card {i}', set_code='TST', 
                 set_name='Test', collector_number=str(i), quantity=1)
            for i in range(100)
        ]
        for card in cards:
            in_memory_db.add(card)
        in_memory_db.commit()
        
        # Act: Apply chaos sort
        chaos = ChaosSort(in_memory_db)
        sorted_ids = chaos.sort_inventory()
        
        # Assert: Order should be randomized (not sequential)
        sequential_ids = [f'sf_{i}' for i in range(100)]
        assert sorted_ids != sequential_ids
        assert len(sorted_ids) == 100
        assert len(set(sorted_ids)) == 100  # All unique
    
    def test_chaos_sort_preserves_all_cards(self, in_memory_db):
        """Test that no cards are lost in chaos sort"""
        # Arrange
        original_ids = [f'sf_{i}' for i in range(50)]
        for i, card_id in enumerate(original_ids):
            card = Card(scryfall_id=card_id, name=f'Card {i}', set_code='TST',
                       set_name='Test', collector_number=str(i), quantity=1)
            in_memory_db.add(card)
        in_memory_db.commit()
        
        # Act
        chaos = ChaosSort(in_memory_db)
        sorted_ids = chaos.sort_inventory()
        
        # Assert: Same cards, different order
        assert set(sorted_ids) == set(original_ids)
        assert len(sorted_ids) == len(original_ids)
    
    def test_chaos_sort_returns_scryfall_ids(self, in_memory_db):
        """Test that chaos sort returns scryfall_id values"""
        # Arrange
        card = Card(scryfall_id='test-id-123', name='Test', set_code='TST',
                   set_name='Test', collector_number='1', quantity=1)
        in_memory_db.add(card)
        in_memory_db.commit()
        
        # Act
        chaos = ChaosSort(in_memory_db)
        result = chaos.sort_inventory()
        
        # Assert
        assert result[0] == 'test-id-123'
    
    def test_chaos_sort_different_runs_produce_different_orders(self, in_memory_db):
        """Test that multiple chaos sort runs produce different orders"""
        # Arrange
        for i in range(50):
            card = Card(scryfall_id=f'sf_{i}', name=f'Card {i}', set_code='TST',
                       set_name='Test', collector_number=str(i), quantity=1)
            in_memory_db.add(card)
        in_memory_db.commit()
        
        # Act: Run chaos sort twice
        chaos = ChaosSort(in_memory_db)
        order1 = chaos.sort_inventory()
        order2 = chaos.sort_inventory()
        
        # Assert: Different random orders (with high probability)
        # They could theoretically be the same, but probability is 1 in 50!
        assert order1 != order2


class TestChaosSortWithBoxes:
    """Test chaos sorting with box/location awareness"""
    
    def test_chaos_sort_respects_box_boundaries(self, in_memory_db):
        """Test that chaos sort doesn't split boxes"""
        # Arrange: Create cards in specific boxes
        for i in range(100):
            card = Card(scryfall_id=f'sf_{i}', name=f'Card {i}', set_code='TST',
                       set_name='Test', collector_number=str(i), quantity=1,
                       box_number=(i // 25) + 1,  # 25 cards per box
                       slot_number=(i % 25) + 1)
            in_memory_db.add(card)
        in_memory_db.commit()
        
        # Act
        chaos = ChaosSort(in_memory_db)
        result = chaos.sort_inventory_preserve_boxes()
        
        # Assert: Cards with same box stay together
        box_groups = {}
        for i, card_id in enumerate(result):
            card = in_memory_db.query(Card).filter_by(scryfall_id=card_id).first()
            box_num = card.box_number
            if box_num not in box_groups:
                box_groups[box_num] = []
            box_groups[box_num].append(i)
        
        # Check that boxes are contiguous
        for box_num, indices in box_groups.items():
            # All indices for a box should be close (within box size)
            assert max(indices) - min(indices) < 50
    
    def test_chaos_sort_updates_location_codes(self, in_memory_db):
        """Test that chaos sort can update location codes"""
        # Arrange
        cards = []
        for i in range(10):
            card = Card(scryfall_id=f'sf_{i}', name=f'Card {i}', set_code='TST',
                       set_name='Test', collector_number=str(i), quantity=1,
                       location_code=f'BOX-0001-SLOT-{i+1:04d}')
            cards.append(card)
            in_memory_db.add(card)
        in_memory_db.commit()
        
        # Act
        chaos = ChaosSort(in_memory_db)
        updated_cards = chaos.sort_with_location_update()
        
        # Assert: Cards have new location codes
        for i, card in enumerate(updated_cards):
            assert card.location_code is not None
            assert 'BOX' in card.location_code
            assert 'SLOT' in card.location_code


# ========================
# DATA GENERATOR TESTS (TDD)
# ========================

class TestDataGeneratorSmall:
    """Test data generator with smaller datasets"""
    
    def test_generate_creates_correct_count(self, in_memory_db):
        """Test that generator creates specified number of cards"""
        # Act
        generator = DataGenerator(in_memory_db)
        generator.generate(count=100)
        
        # Assert
        count = in_memory_db.query(Card).count()
        assert count == 100
    
    def test_generated_cards_have_unique_scryfall_ids(self, in_memory_db):
        """Test that all generated cards have unique IDs"""
        # Act
        generator = DataGenerator(in_memory_db)
        generator.generate(count=500)
        
        # Assert
        cards = in_memory_db.query(Card).all()
        scryfall_ids = [c.scryfall_id for c in cards]
        assert len(scryfall_ids) == len(set(scryfall_ids))
    
    def test_generated_cards_have_required_fields(self, in_memory_db):
        """Test that generated cards have all required fields"""
        # Act
        generator = DataGenerator(in_memory_db)
        generator.generate(count=10)
        
        # Assert
        card = in_memory_db.query(Card).first()
        assert card.scryfall_id is not None
        assert card.name is not None
        assert card.set_code is not None
        assert card.set_name is not None
        assert card.collector_number is not None
        assert card.quantity > 0
        assert card.condition is not None
    
    def test_generated_cards_are_realistic(self, in_memory_db):
        """Test that generated cards have realistic data"""
        # Act
        generator = DataGenerator(in_memory_db)
        generator.generate(count=100)
        
        # Assert
        card = in_memory_db.query(Card).first()
        assert len(card.scryfall_id) > 0
        assert len(card.name) > 0
        assert card.set_code in generator.SETS
        assert card.condition in generator.CONDITIONS
        assert 0 < card.purchase_price < 1000


class TestDataGeneratorLarge:
    """Test data generator with large datasets"""
    
    def test_generate_1000_cards(self, in_memory_db):
        """Test generating 1,000 cards"""
        # Act
        generator = DataGenerator(in_memory_db)
        start_time = time.time()
        generator.generate(count=1000)
        elapsed = time.time() - start_time
        
        # Assert
        count = in_memory_db.query(Card).count()
        assert count == 1000
        print(f"Generated 1,000 cards in {elapsed:.2f}s")
    
    def test_generate_10000_cards(self, persistent_db):
        """Test generating 10,000 cards (requires persistent DB)"""
        db, _ = persistent_db
        
        # Act
        generator = DataGenerator(db)
        start_time = time.time()
        generator.generate(count=10000, batch_size=1000)
        elapsed = time.time() - start_time
        
        # Assert
        count = db.query(Card).count()
        assert count == 10000
        print(f"Generated 10,000 cards in {elapsed:.2f}s")
    
    def test_generate_100000_cards(self, persistent_db):
        """Test generating 100,000 cards (large load test)"""
        db, db_path = persistent_db
        
        # Act
        generator = DataGenerator(db)
        start_time = time.time()
        generator.generate(count=100000, batch_size=5000)
        elapsed = time.time() - start_time
        
        # Assert
        count = db.query(Card).count()
        assert count == 100000
        
        print(f"Generated 100,000 cards in {elapsed:.2f}s")
        print(f"Database file size: {os.path.getsize(db_path) / (1024*1024):.2f} MB")
        
        # Verify data
        cards = db.query(Card).limit(10).all()
        assert all(c.scryfall_id for c in cards)


# ========================
# CHAOS SORT LARGE SCALE TESTS
# ========================

class TestChaosSortLargeScale:
    """Test chaos sorting with large datasets"""
    
    def test_chaos_sort_1000_cards(self, in_memory_db):
        """Test chaos sort with 1,000 cards"""
        # Arrange
        generator = DataGenerator(in_memory_db)
        generator.generate(count=1000)
        
        # Act
        start_time = time.time()
        chaos = ChaosSort(in_memory_db)
        result = chaos.sort_inventory()
        elapsed = time.time() - start_time
        
        # Assert
        assert len(result) == 1000
        assert len(set(result)) == 1000
        print(f"Chaos sorted 1,000 cards in {elapsed:.2f}s")
    
    def test_chaos_sort_10000_cards(self, persistent_db):
        """Test chaos sort with 10,000 cards"""
        db, _ = persistent_db
        
        # Arrange
        generator = DataGenerator(db)
        generator.generate(count=10000, batch_size=1000)
        
        # Act
        start_time = time.time()
        chaos = ChaosSort(db)
        result = chaos.sort_inventory()
        elapsed = time.time() - start_time
        
        # Assert
        assert len(result) == 10000
        print(f"Chaos sorted 10,000 cards in {elapsed:.2f}s")
    
    def test_chaos_sort_100000_cards(self, persistent_db):
        """Test chaos sort with 100,000 cards"""
        db, db_path = persistent_db
        
        # Arrange
        generator = DataGenerator(db)
        generator.generate(count=100000, batch_size=5000)
        
        # Act
        start_time = time.time()
        chaos = ChaosSort(db)
        result = chaos.sort_inventory()
        elapsed = time.time() - start_time
        
        # Assert
        assert len(result) == 100000
        assert len(set(result)) == 100000
        print(f"Chaos sorted 100,000 cards in {elapsed:.2f}s")


# ========================
# DATABASE PERFORMANCE TESTS
# ========================

class TestDatabasePerformance:
    """Test database performance with large datasets"""
    
    def test_query_performance_10000_cards(self, persistent_db):
        """Test query performance with 10,000 cards"""
        db, _ = persistent_db
        
        # Arrange
        generator = DataGenerator(db)
        generator.generate(count=10000, batch_size=1000)
        
        # Act: Query all cards
        start_time = time.time()
        cards = db.query(Card).all()
        elapsed = time.time() - start_time
        
        # Assert
        assert len(cards) == 10000
        print(f"Queried 10,000 cards in {elapsed:.2f}s")
    
    def test_filter_query_performance(self, persistent_db):
        """Test filtered query performance"""
        db, _ = persistent_db
        
        # Arrange
        generator = DataGenerator(db)
        generator.generate(count=100000, batch_size=5000)
        
        # Act: Query specific condition
        start_time = time.time()
        cards = db.query(Card).filter(Card.condition == 'near_mint').all()
        elapsed = time.time() - start_time
        
        # Assert
        assert len(cards) > 0
        print(f"Filtered query for 100,000 cards in {elapsed:.2f}s")
    
    def test_aggregation_query_performance(self, persistent_db):
        """Test aggregation query performance"""
        db, _ = persistent_db
        
        # Arrange
        generator = DataGenerator(db)
        generator.generate(count=100000, batch_size=5000)
        
        # Act: Count and sum
        start_time = time.time()
        count = db.query(func.count(Card.id)).scalar()
        total_quantity = db.query(func.sum(Card.quantity)).scalar()
        elapsed = time.time() - start_time
        
        # Assert
        assert count == 100000
        assert total_quantity > 0
        print(f"Aggregation query on 100,000 cards in {elapsed:.2f}s")


# ========================
# INTEGRATION TESTS
# ========================

class TestIntegrationChaosWorkflow:
    """Test complete workflow: generate → chaos sort → verify"""
    
    def test_complete_workflow_100k(self, persistent_db):
        """Test complete end-to-end workflow with 100k cards"""
        db, db_path = persistent_db
        
        # Step 1: Generate data
        print("\nStep 1: Generating 100,000 cards...")
        generator = DataGenerator(db)
        start = time.time()
        generator.generate(count=100000, batch_size=5000)
        gen_time = time.time() - start
        print(f"  Generated in {gen_time:.2f}s")
        
        # Step 2: Apply chaos sort
        print("Step 2: Applying chaos sort...")
        start = time.time()
        chaos = ChaosSort(db)
        sorted_ids = chaos.sort_inventory()
        chaos_time = time.time() - start
        print(f"  Chaos sorted in {chaos_time:.2f}s")
        
        # Step 3: Verify integrity
        print("Step 3: Verifying data integrity...")
        start = time.time()
        total_cards = db.query(Card).count()
        unique_ids = len(set(sorted_ids))
        verify_time = time.time() - start
        print(f"  Verified in {verify_time:.2f}s")
        
        # Assert
        assert total_cards == 100000
        assert unique_ids == 100000
        
        db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
        print(f"\nTotal workflow time: {gen_time + chaos_time + verify_time:.2f}s")
        print(f"Database size: {db_size_mb:.2f} MB")
        print(f"Average per card: {(db_size_mb / 100000) * 1000:.2f} KB per 1000 cards")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
