import pytest
import os
import tempfile
from io import BytesIO
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd

# Add the mtg-inventory directory to the path
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app import app
from database import Base, SessionLocal
from models import Card, Box
from routes.inventory import bp as inventory_bp
from services.manabox import import_csv
from services.location_engine import assign_location


@pytest.fixture
def test_app():
    """Create a test Flask app with a test database."""
    app.config['TESTING'] = True
    
    # Use in-memory SQLite database for testing
    test_db_path = ':memory:'
    
    # Override the database connection
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine(f'sqlite:///{test_db_path}')
    Base.metadata.create_all(bind=engine)
    
    # Monkey patch the SessionLocal
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    import database
    original_session = database.SessionLocal
    database.SessionLocal = TestingSessionLocal
    
    # Also patch in routes.inventory
    import routes.inventory as inventory_module
    inventory_module.SessionLocal = TestingSessionLocal
    
    # Also patch in services.manabox
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
    """Create a test client."""
    app, _, _ = test_app
    return app.test_client()


@pytest.fixture
def db_session(test_app):
    """Create a test database session."""
    _, SessionLocal, _ = test_app
    db = SessionLocal()
    yield db
    db.close()


def create_test_csv(data=None):
    """Create a test CSV file."""
    if data is None:
        data = {
            'Name': ['Path to Exile', 'Lightning Bolt'],
            'Set code': ['SLD', 'LEA'],
            'Set name': ['Secret Lair Drop', 'Limited Edition Alpha'],
            'Collector number': ['226', '244'],
            'Foil': ['normal', 'normal'],
            'Rarity': ['rare', 'common'],
            'Quantity': [1, 2],
            'ManaBox ID': ['64698', '12345'],
            'Scryfall ID': ['4e2fe951-4820-4555-8cee-621c66ed8620', 'c8d672ba-83bd-4bf0-b8f4-5eb382f16a62'],
            'Purchase price': [15.27, 5.00],
            'Condition': ['near_mint', 'good'],
            'Language': ['en', 'en'],
        }
    
    df = pd.DataFrame(data)
    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    return csv_buffer


class TestImportEndpoint:
    """Tests for the /inventory/import endpoint."""
    
    def test_import_post_no_file(self, client):
        """Test POST request without a file."""
        response = client.post('/inventory/import', follow_redirects=True)
        assert response.status_code == 200
        # Should show error message
        assert b'No file part' in response.data or b'No selected file' in response.data
    
    def test_import_post_empty_filename(self, client):
        """Test POST request with empty filename."""
        response = client.post(
            '/inventory/import',
            data={'file': (BytesIO(b''), '')},
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'No selected file' in response.data
    
    def test_import_post_invalid_file_type(self, client):
        """Test POST request with a non-CSV file."""
        response = client.post(
            '/inventory/import',
            data={'file': (BytesIO(b'test data'), 'test.txt')},
            follow_redirects=True
        )
        assert response.status_code == 200
        # Should redirect without processing
    
    def test_import_post_valid_csv(self, client, db_session):
        """Test POST request with a valid CSV file."""
        csv_file = create_test_csv()
        response = client.post(
            '/inventory/import',
            data={'file': (csv_file, 'test.csv')},
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'Import successful' in response.data
        
        # Check that cards were added
        cards = db_session.query(Card).all()
        assert len(cards) == 2
        assert cards[0].name == 'Path to Exile'
        assert cards[1].name == 'Lightning Bolt'
    
    def test_import_post_csv_with_missing_scryfall_id(self, client, db_session):
        """Test POST with CSV containing rows with missing scryfall_id."""
        data = {
            'Name': ['Path to Exile', 'Unknown Card'],
            'Set code': ['SLD', 'UNK'],
            'Set name': ['Secret Lair Drop', 'Unknown'],
            'Collector number': ['226', '001'],
            'Foil': ['normal', 'normal'],
            'Rarity': ['rare', 'common'],
            'Quantity': [1, 1],
            'ManaBox ID': ['64698', ''],
            'Scryfall ID': ['4e2fe951-4820-4555-8cee-621c66ed8620', ''],
            'Purchase price': [15.27, 0.0],
            'Condition': ['near_mint', 'good'],
            'Language': ['en', 'en'],
        }
        csv_file = create_test_csv(data)
        response = client.post(
            '/inventory/import',
            data={'file': (csv_file, 'test.csv')},
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'Import successful' in response.data
        assert b'1 added' in response.data
        assert b'1 skipped' in response.data
    
    def test_import_get_shows_form(self, client):
        """Test GET request shows the import form."""
        response = client.get('/inventory/import')
        assert response.status_code == 200
        assert b'import' in response.data.lower() or b'file' in response.data.lower()


class TestLocationEngine:
    """Tests for the location assignment logic."""
    
    def test_assign_location_first_box_creation(self, db_session):
        """Test that the first box is created correctly when no boxes exist."""
        # Create a new card
        card = Card(
            scryfall_id='test-id-1',
            name='Test Card',
            set_code='TST',
            set_name='Test Set',
            collector_number='1',
            quantity=1,
        )
        
        # This should not raise an error even when no boxes exist
        assign_location(db_session, card)
        
        # Check that a box was created
        boxes = db_session.query(Box).all()
        assert len(boxes) == 1
        assert boxes[0].box_number == 1
        assert boxes[0].current_count == 1
        
        # Check that card was assigned to the box
        assert card.box_number == 1
        assert card.slot_number == 1
        assert card.location_code == 'BOX-0001-SLOT-0001'
    
    def test_assign_location_multiple_cards_same_box(self, db_session):
        """Test that multiple cards are assigned to the same box."""
        card1 = Card(
            scryfall_id='test-id-1',
            name='Test Card 1',
            set_code='TST',
            set_name='Test Set',
            collector_number='1',
            quantity=1,
        )
        card2 = Card(
            scryfall_id='test-id-2',
            name='Test Card 2',
            set_code='TST',
            set_name='Test Set',
            collector_number='2',
            quantity=1,
        )
        
        assign_location(db_session, card1)
        assign_location(db_session, card2)
        
        # Both cards should be in the same box
        assert card1.box_number == card2.box_number == 1
        assert card1.slot_number == 1
        assert card2.slot_number == 2
    
    def test_assign_location_box_overflow(self, db_session):
        """Test that a new box is created when the current box is full."""
        # Set a small box capacity for testing
        from config import Config
        original_capacity = Config.BOX_CAPACITY
        Config.BOX_CAPACITY = 2
        
        try:
            card1 = Card(
                scryfall_id='test-id-1',
                name='Test Card 1',
                set_code='TST',
                set_name='Test Set',
                collector_number='1',
                quantity=1,
            )
            card2 = Card(
                scryfall_id='test-id-2',
                name='Test Card 2',
                set_code='TST',
                set_name='Test Set',
                collector_number='2',
                quantity=1,
            )
            card3 = Card(
                scryfall_id='test-id-3',
                name='Test Card 3',
                set_code='TST',
                set_name='Test Set',
                collector_number='3',
                quantity=1,
            )
            
            assign_location(db_session, card1)
            assign_location(db_session, card2)
            assign_location(db_session, card3)
            
            # First two cards should be in box 1, third in box 2
            assert card1.box_number == 1
            assert card2.box_number == 1
            assert card3.box_number == 2
            
            boxes = db_session.query(Box).all()
            assert len(boxes) == 2
            assert boxes[0].current_count == 2
            assert boxes[1].current_count == 1
        finally:
            Config.BOX_CAPACITY = original_capacity


class TestImportService:
    """Tests for the import_csv service."""
    
    def test_import_csv_creates_cards(self, db_session):
        """Test that import_csv correctly creates cards."""
        csv_file = create_test_csv()
        result = import_csv(db_session, csv_file)
        
        assert result['added'] == 2
        assert result['updated'] == 0
        assert result['skipped'] == 0
        
        cards = db_session.query(Card).all()
        assert len(cards) == 2
    
    def test_import_csv_updates_existing_cards(self, db_session):
        """Test that import_csv updates existing cards."""
        # Create an existing card
        existing_card = Card(
            scryfall_id='4e2fe951-4820-4555-8cee-621c66ed8620',
            name='Path to Exile',
            set_code='SLD',
            set_name='Secret Lair Drop',
            collector_number='226',
            quantity=1,
            condition='good',
        )
        db_session.add(existing_card)
        db_session.commit()
        
        # Import with updated quantity and condition
        data = {
            'Name': ['Path to Exile'],
            'Set code': ['SLD'],
            'Set name': ['Secret Lair Drop'],
            'Collector number': ['226'],
            'Foil': ['normal'],
            'Rarity': ['rare'],
            'Quantity': [5],
            'ManaBox ID': ['64698'],
            'Scryfall ID': ['4e2fe951-4820-4555-8cee-621c66ed8620'],
            'Purchase price': [15.27],
            'Condition': ['near_mint'],
            'Language': ['en'],
        }
        csv_file = create_test_csv(data)
        result = import_csv(db_session, csv_file)
        
        assert result['added'] == 0
        assert result['updated'] == 1
        assert result['skipped'] == 0
        
        # Check that the card was updated
        card = db_session.query(Card).filter_by(scryfall_id='4e2fe951-4820-4555-8cee-621c66ed8620').first()
        assert card.quantity == 5
        assert card.condition == 'near_mint'
    
    def test_import_csv_missing_required_column(self, db_session):
        """Test that import_csv raises an error for missing required columns."""
        data = {
            'Name': ['Path to Exile'],
            'Set code': ['SLD'],
            # Missing other required columns
        }
        csv_file = create_test_csv(data)
        
        with pytest.raises(ValueError, match="Missing required column"):
            import_csv(db_session, csv_file)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
