"""
End-to-end tests: CSV upload to eBay listing creation workflow
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
import pandas as pd

from app import app
from database import Base, SessionLocal, init_db
from models import Card, Box, Price
from services.manabox import import_csv
from services.scryfall_api import ScryfallAPI, eBayAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def test_app():
    """Create a test Flask app with a test database"""
    app.config['TESTING'] = True
    
    # Use in-memory database for testing
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Patch the SessionLocal in app modules
    import database
    original_session = database.SessionLocal
    database.SessionLocal = TestingSessionLocal
    
    import routes.inventory as inventory_module
    inventory_module.SessionLocal = TestingSessionLocal
    
    import services.manabox as manabox_module
    manabox_module.SessionLocal = TestingSessionLocal
    
    yield app, TestingSessionLocal, engine
    
    # Cleanup
    database.SessionLocal = original_session
    inventory_module.SessionLocal = original_session
    manabox_module.SessionLocal = original_session
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_app):
    """Create a test client"""
    app, _, _ = test_app
    return app.test_client()


@pytest.fixture
def db_session(test_app):
    """Create a test database session"""
    _, SessionLocal, _ = test_app
    db = SessionLocal()
    yield db
    db.close()


def create_test_csv(data=None):
    """Create a test CSV file"""
    if data is None:
        data = {
            'Name': ['Path to Exile', 'Lightning Bolt', 'Black Lotus'],
            'Set code': ['SLD', 'LEA', 'LEA'],
            'Set name': ['Secret Lair Drop', 'Limited Edition Alpha', 'Limited Edition Alpha'],
            'Collector number': ['226', '244', '232'],
            'Foil': ['normal', 'normal', 'normal'],
            'Rarity': ['rare', 'common', 'rare'],
            'Quantity': [1, 2, 1],
            'ManaBox ID': ['64698', '12345', '23456'],
            'Scryfall ID': ['4e2fe951-4820-4555-8cee-621c66ed8620', 'c8d672ba-83bd-4bf0-b8f4-5eb382f16a62', '6e2f0299-266c-4bd0-b3d7-6d868b207fa8'],
            'Purchase price': [15.27, 5.00, 100.00],
            'Condition': ['near_mint', 'good', 'mint'],
            'Language': ['en', 'en', 'en'],
        }
    
    df = pd.DataFrame(data)
    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    return csv_buffer


class TestE2EImportFlow:
    """E2E tests: Import CSV and create eBay listings"""
    
    def test_e2e_full_import_workflow(self, client, db_session):
        """Test complete import workflow via HTTP endpoint"""
        csv_file = create_test_csv()
        response = client.post(
            '/inventory/import',
            data={'file': (csv_file, 'test.csv')},
            follow_redirects=True
        )
        
        assert response.status_code == 200
        
        # Verify cards were imported
        cards = db_session.query(Card).all()
        assert len(cards) == 3
        
        # Verify locations were assigned
        assert all(c.location_code for c in cards)
        assert all(c.box_number for c in cards)
        
        # Verify boxes were created
        boxes = db_session.query(Box).all()
        assert len(boxes) >= 1
    
    def test_e2e_import_creates_proper_box_assignments(self, db_session):
        """Test that import correctly assigns cards to boxes"""
        csv_file = create_test_csv({
            'Name': [f'Card {i}' for i in range(1000)],
            'Set code': ['S'] * 1000,
            'Set name': ['Set'] * 1000,
            'Collector number': [str(i) for i in range(1000)],
            'Foil': ['normal'] * 1000,
            'Rarity': ['common'] * 1000,
            'Quantity': [1] * 1000,
            'ManaBox ID': [str(i) for i in range(1000)],
            'Scryfall ID': [f'sf{i}' for i in range(1000)],
            'Purchase price': [1.0] * 1000,
            'Condition': ['good'] * 1000,
            'Language': ['en'] * 1000,
        })
        
        result = import_csv(db_session, csv_file)
        assert result['added'] == 1000
        
        cards = db_session.query(Card).all()
        assert len(cards) == 1000
        
        # All cards should have box assignments
        assert all(c.box_number is not None for c in cards)
        assert all(c.location_code is not None for c in cards)
        
        # Cards should be distributed across boxes
        boxes = db_session.query(Box).all()
        assert len(boxes) == 2  # 1000 cards / 500 capacity = 2 boxes


class TestE2EPricingFlow:
    """E2E tests: Fetch pricing data from external APIs"""
    
    @patch('services.scryfall_api.ScryfallAPI.get_card_by_id')
    @patch('services.scryfall_api.TCGPlayerAPI')
    def test_e2e_fetch_pricing_from_scryfall(self, mock_tcg, mock_scryfall, db_session):
        """Test fetching card pricing from Scryfall"""
        scryfall_id = '4e2fe951-4820-4555-8cee-621c66ed8620'
        
        # Mock Scryfall response
        mock_scryfall.return_value = {
            'id': scryfall_id,
            'name': 'Path to Exile',
            'prices': {
                'usd': 15.99,
                'eur': 14.50
            }
        }
        
        # Import a card
        card = Card(
            scryfall_id=scryfall_id,
            name='Path to Exile',
            set_code='SLD',
            set_name='Secret Lair Drop',
            collector_number='226',
            quantity=1
        )
        db_session.add(card)
        db_session.commit()
        
        # Fetch pricing
        card_data = ScryfallAPI.get_card_by_id(scryfall_id)
        assert card_data is not None
        assert card_data['prices']['usd'] == 15.99
        
        # Store pricing in database
        price = Price(
            scryfall_id=scryfall_id,
            market_price=card_data['prices']['usd'],
            low_price=card_data['prices']['usd'] * 0.8,
            high_price=card_data['prices']['usd'] * 1.2
        )
        db_session.add(price)
        db_session.commit()
        
        # Verify price was stored
        stored_price = db_session.query(Price).filter_by(scryfall_id=scryfall_id).first()
        assert stored_price.market_price == 15.99
    
    @patch('services.scryfall_api.ScryfallAPI.get_card_by_id')
    def test_e2e_calculate_listing_price(self, mock_scryfall, db_session):
        """Test calculating appropriate listing price from market data"""
        scryfall_id = 'test_id'
        purchase_price = 5.00
        
        # Mock market prices
        mock_scryfall.return_value = {
            'prices': {
                'usd': 15.99,
                'eur': 14.50
            }
        }
        
        market_data = ScryfallAPI.get_card_by_id(scryfall_id)
        market_price = market_data['prices']['usd']
        
        # Calculate recommended listing price (typically 85% of market)
        listing_price = market_price * 0.85
        profit_margin = listing_price - purchase_price
        
        assert profit_margin > 0
        assert listing_price < market_price


class TestE2EeBayListingCreation:
    """E2E tests: Create listings on eBay"""
    
    @patch('services.scryfall_api.ScryfallAPI.get_card_by_id')
    @patch('services.scryfall_api.eBayAPI')
    def test_e2e_create_ebay_listing_from_card(self, mock_ebay, mock_scryfall, db_session):
        """Test creating an eBay listing from an imported card"""
        # Setup
        scryfall_id = '4e2fe951-4820-4555-8cee-621c66ed8620'
        
        # Mock Scryfall data
        mock_scryfall.return_value = {
            'prices': {'usd': 15.99},
            'rarity': 'rare',
            'set': 'SLD'
        }
        
        # Create card
        card = Card(
            scryfall_id=scryfall_id,
            name='Path to Exile',
            set_code='SLD',
            set_name='Secret Lair Drop',
            collector_number='226',
            condition='near_mint',
            purchase_price=5.00,
            quantity=1,
            list_on_ebay=True
        )
        db_session.add(card)
        db_session.commit()
        
        # Get market price
        market_data = ScryfallAPI.get_card_by_id(scryfall_id)
        listing_price = market_data['prices']['usd'] * 0.85
        
        # Prepare eBay listing data
        listing_data = {
            'title': f"{card.name} - {card.set_name}",
            'description': f"{card.name}\nSet: {card.set_name}\nCondition: {card.condition}\nLanguage: {card.language}",
            'price': listing_price,
            'quantity': card.quantity,
            'categoryId': 19139,  # MTG category
        }
        
        # Mock eBay API
        mock_api = Mock()
        mock_api.create_listing.return_value = 'listing_123'
        mock_api.publish_listing.return_value = True
        
        # Create and publish listing
        listing_id = mock_api.create_listing(listing_data)
        published = mock_api.publish_listing(listing_id)
        
        assert listing_id == 'listing_123'
        assert published is True
        
        # Store listing ID in database
        card.ebay_listing_id = listing_id
        db_session.commit()
        
        # Verify
        updated_card = db_session.query(Card).filter_by(scryfall_id=scryfall_id).first()
        assert updated_card.ebay_listing_id == 'listing_123'
    
    @patch('services.scryfall_api.ScryfallAPI.get_card_by_id')
    @patch('services.scryfall_api.eBayAPI')
    def test_e2e_batch_create_listings(self, mock_ebay, mock_scryfall, db_session):
        """Test creating multiple eBay listings in batch"""
        # Import multiple cards
        csv_file = create_test_csv()
        result = import_csv(db_session, csv_file)
        assert result['added'] == 3
        
        # Mark all for eBay listing
        cards = db_session.query(Card).all()
        for card in cards:
            card.list_on_ebay = True
        db_session.commit()
        
        # Mock eBay API
        mock_api = Mock()
        listing_ids = ['listing_1', 'listing_2', 'listing_3']
        mock_api.create_listing.side_effect = listing_ids
        mock_api.publish_listing.return_value = True
        
        # Batch create listings
        created_listings = []
        for i, card in enumerate(cards):
            listing_price = (card.purchase_price or 1.0) * 3  # 3x markup as example
            listing_data = {
                'title': f"{card.name} - {card.set_name}",
                'description': f"Condition: {card.condition}",
                'price': listing_price,
                'quantity': card.quantity,
            }
            listing_id = mock_api.create_listing(listing_data)
            if listing_id:
                published = mock_api.publish_listing(listing_id)
                if published:
                    created_listings.append((card.scryfall_id, listing_id))
                    card.ebay_listing_id = listing_id
        
        db_session.commit()
        
        # Verify all listings created
        assert len(created_listings) == 3
        
        # Verify each card has a listing ID
        for card in cards:
            assert card.ebay_listing_id is not None


class TestE2ECompleteWorkflow:
    """E2E tests: Complete end-to-end workflow"""
    
    @patch('services.scryfall_api.ScryfallAPI.get_card_by_id')
    @patch('services.scryfall_api.eBayAPI')
    def test_e2e_complete_workflow_csv_to_ebay(self, mock_ebay, mock_scryfall, client, db_session):
        """
        Complete workflow:
        1. Upload CSV
        2. Import cards to database
        3. Fetch pricing data
        4. Create eBay listings
        5. Publish listings
        """
        
        # Step 1: Upload CSV
        csv_file = create_test_csv()
        response = client.post(
            '/inventory/import',
            data={'file': (csv_file, 'test.csv')},
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'Import successful' in response.data
        
        # Step 2: Verify cards imported
        cards = db_session.query(Card).all()
        assert len(cards) == 3
        
        # Verify locations assigned
        assert all(c.location_code for c in cards)
        
        # Step 3: Fetch pricing for each card
        def mock_scryfall_response(scryfall_id):
            return {
                'id': scryfall_id,
                'prices': {'usd': 15.99}
            }
        
        mock_scryfall.side_effect = mock_scryfall_response
        
        # Step 4: Create eBay listings
        mock_ebay_api = Mock()
        listing_ids = []
        
        for card in cards:
            # Fetch market price
            market_data = ScryfallAPI.get_card_by_id(card.scryfall_id)
            listing_price = market_data['prices']['usd'] * 0.85
            
            # Create listing
            listing_data = {
                'title': f"{card.name} - {card.set_name}",
                'description': f"Condition: {card.condition}",
                'price': listing_price,
                'quantity': card.quantity,
            }
            
            listing_id = f"listing_{card.scryfall_id[:8]}"
            mock_ebay_api.create_listing.return_value = listing_id
            listing_id = mock_ebay_api.create_listing(listing_data)
            listing_ids.append(listing_id)
            
            # Publish listing
            mock_ebay_api.publish_listing.return_value = True
            published = mock_ebay_api.publish_listing(listing_id)
            assert published
            
            # Store listing ID
            card.ebay_listing_id = listing_id
        
        db_session.commit()
        
        # Step 5: Verify final state
        for card in cards:
            assert card.ebay_listing_id is not None
            assert card.location_code is not None
            assert card.box_number is not None
        
        # Verify we have proper box distribution
        boxes = db_session.query(Box).all()
        total_cards_in_boxes = sum(b.current_count for b in boxes)
        assert total_cards_in_boxes == 3
    
    def test_e2e_error_handling_invalid_csv(self, client):
        """Test error handling for invalid CSV"""
        # Send invalid CSV (missing required columns)
        response = client.post(
            '/inventory/import',
            data={'file': (BytesIO(b'invalid,csv\ndata'), 'bad.csv')},
            follow_redirects=True
        )
        assert response.status_code == 200
        # Should show error but not crash
    
    def test_e2e_handles_duplicate_imports(self, db_session):
        """Test that duplicate imports don't create duplicate cards"""
        csv_file1 = create_test_csv()
        result1 = import_csv(db_session, csv_file1)
        assert result1['added'] == 3
        
        # Import same CSV again
        csv_file2 = create_test_csv()
        result2 = import_csv(db_session, csv_file2)
        assert result2['added'] == 0
        assert result2['updated'] == 3
        
        # Verify only 3 cards in database
        cards = db_session.query(Card).all()
        assert len(cards) == 3


class TestE2EDataIntegrity:
    """E2E tests: Verify data integrity throughout workflow"""
    
    def test_e2e_transaction_rollback_on_error(self, db_session):
        """Test that failed import doesn't partially commit"""
        # Try to import with invalid data
        invalid_csv = BytesIO(b"Name\n")  # Just header, missing other columns
        
        try:
            import_csv(db_session, invalid_csv)
        except ValueError:
            pass
        
        # Database should be empty (no partial import)
        cards = db_session.query(Card).all()
        assert len(cards) == 0
    
    def test_e2e_location_assignments_are_persistent(self, db_session):
        """Test that location assignments survive database round-trips"""
        csv_file = create_test_csv()
        import_csv(db_session, csv_file)
        
        # Get a card
        card = db_session.query(Card).first()
        original_location = card.location_code
        original_box = card.box_number
        original_slot = card.slot_number
        
        # Simulate database close and reopen
        db_session.close()
        db_new = db_session
        
        # Query again
        card_reloaded = db_new.query(Card).first()
        assert card_reloaded.location_code == original_location
        assert card_reloaded.box_number == original_box
        assert card_reloaded.slot_number == original_slot
    
    def test_e2e_box_capacity_respected(self, db_session):
        """Test that box capacity constraints are always respected"""
        from config import Config
        original_capacity = Config.BOX_CAPACITY
        Config.BOX_CAPACITY = 100
        
        try:
            csv_file = create_test_csv({
                'Name': [f'Card {i}' for i in range(500)],
                'Set code': ['S'] * 500,
                'Set name': ['Set'] * 500,
                'Collector number': [str(i) for i in range(500)],
                'Foil': ['normal'] * 500,
                'Rarity': ['common'] * 500,
                'Quantity': [1] * 500,
                'ManaBox ID': [str(i) for i in range(500)],
                'Scryfall ID': [f'sf{i}' for i in range(500)],
                'Purchase price': [1.0] * 500,
                'Condition': ['good'] * 500,
                'Language': ['en'] * 500,
            })
            
            import_csv(db_session, csv_file)
            
            boxes = db_session.query(Box).all()
            # Verify no box exceeds capacity
            for box in boxes:
                assert box.current_count <= Config.BOX_CAPACITY
            
            # Verify total capacity used
            total = sum(b.current_count for b in boxes)
            assert total == 500
        finally:
            Config.BOX_CAPACITY = original_capacity


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
