"""
Unit tests for all services
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from io import BytesIO
import pandas as pd

from services.manabox import import_csv
from services.location_engine import assign_location
from services.scryfall_api import ScryfallAPI, eBayAPI
from models import Card, Box
from database import Base, SessionLocal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def test_db():
    """Create an in-memory test database"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()
    yield db
    db.close()


# ========================
# SCRYFALL API TESTS
# ========================

class TestScryfallAPI:
    """Tests for Scryfall API client"""
    
    @patch('services.scryfall_api.requests.get')
    def test_get_card_by_id_success(self, mock_get):
        """Test successful card fetch by ID"""
        mock_get.return_value.json.return_value = {
            'id': '4e2fe951-4820-4555-8cee-621c66ed8620',
            'name': 'Path to Exile',
            'prices': {
                'usd': 15.99,
                'eur': 14.50
            }
        }
        mock_get.return_value.raise_for_status.return_value = None
        
        result = ScryfallAPI.get_card_by_id('4e2fe951-4820-4555-8cee-621c66ed8620')
        
        assert result is not None
        assert result['name'] == 'Path to Exile'
        assert result['prices']['usd'] == 15.99
        mock_get.assert_called_once()
    
    @patch('services.scryfall_api.requests.get')
    def test_get_card_by_id_not_found(self, mock_get):
        """Test card not found"""
        import requests
        mock_get.side_effect = requests.exceptions.RequestException("404")
        
        result = ScryfallAPI.get_card_by_id('invalid-id')
        
        assert result is None
    
    @patch('services.scryfall_api.requests.get')
    def test_search_cards_success(self, mock_get):
        """Test successful card search"""
        mock_get.return_value.json.return_value = {
            'data': [
                {'id': 'id1', 'name': 'Card 1'},
                {'id': 'id2', 'name': 'Card 2'},
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None
        
        result = ScryfallAPI.search_cards('lightning bolt')
        
        assert len(result) == 2
        assert result[0]['name'] == 'Card 1'
        mock_get.assert_called_once()
    
    @patch('services.scryfall_api.requests.get')
    def test_search_cards_empty_result(self, mock_get):
        """Test search with no results"""
        mock_get.return_value.json.return_value = {'data': []}
        mock_get.return_value.raise_for_status.return_value = None
        
        result = ScryfallAPI.search_cards('nonexistent card')
        
        assert result == []
    
    @patch('services.scryfall_api.requests.get')
    def test_search_cards_respects_limit(self, mock_get):
        """Test that search respects the limit parameter"""
        mock_get.return_value.json.return_value = {
            'data': [
                {'id': f'id{i}', 'name': f'Card {i}'} for i in range(20)
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None
        
        result = ScryfallAPI.search_cards('test', limit=5)
        
        assert len(result) == 5



# ========================
# EBAY API TESTS
# ========================

class TesteBayAPI:
    """Tests for eBay API client"""
    
    @patch('services.scryfall_api.requests.post')
    def test_get_access_token_success(self, mock_post):
        """Test successful OAuth token acquisition"""
        with patch('services.scryfall_api.Config') as mock_config:
            mock_config.EBAY_APP_ID = 'app_123'
            mock_config.EBAY_DEV_ID = 'dev_123'
            mock_config.EBAY_USER_TOKEN = None
            mock_config.EBAY_CLIENT_ID = 'client_123'
            mock_config.EBAY_CLIENT_SECRET = 'secret_123'
            mock_config.EBAY_REFRESH_TOKEN = 'refresh_123'
            mock_config.EBAY_SANDBOX_MODE = True
            
            mock_post.return_value.json.return_value = {
                'access_token': 'access_token_xyz'
            }
            mock_post.return_value.raise_for_status.return_value = None
            
            api = eBayAPI()
            token = api.get_access_token()
            
            assert token == 'access_token_xyz'
    
    @patch('services.scryfall_api.requests.post')
    def test_create_listing_success(self, mock_post):
        """Test successful listing creation"""
        with patch('services.scryfall_api.Config') as mock_config:
            mock_config.EBAY_APP_ID = 'app_123'
            mock_config.EBAY_DEV_ID = 'dev_123'
            mock_config.EBAY_USER_TOKEN = None
            mock_config.EBAY_CLIENT_ID = 'client_123'
            mock_config.EBAY_CLIENT_SECRET = 'secret_123'
            mock_config.EBAY_REFRESH_TOKEN = 'refresh_123'
            mock_config.EBAY_SANDBOX_MODE = True
            
            # Mock auth response
            auth_response = Mock()
            auth_response.json.return_value = {'access_token': 'test_token'}
            auth_response.raise_for_status.return_value = None
            
            # Mock listing response
            listing_response = Mock()
            listing_response.status_code = 201
            listing_response.headers = {'Location': 'https://api.ebay.com/sell/inventory/v1/inventory_item/12345xyz'}
            listing_response.raise_for_status.return_value = None
            
            mock_post.side_effect = [auth_response, listing_response]
            
            api = eBayAPI()
            listing_data = {
                'title': 'Path to Exile',
                'description': 'Magic the Gathering card',
                'price': 15.99
            }
            listing_id = api.create_listing(listing_data)
            
            assert listing_id == '12345xyz'
    
    @patch('services.scryfall_api.requests.post')
    def test_publish_listing_success(self, mock_post):
        """Test successful listing publication"""
        with patch('services.scryfall_api.Config') as mock_config:
            mock_config.EBAY_APP_ID = 'app_123'
            mock_config.EBAY_DEV_ID = 'dev_123'
            mock_config.EBAY_USER_TOKEN = None
            mock_config.EBAY_CLIENT_ID = 'client_123'
            mock_config.EBAY_CLIENT_SECRET = 'secret_123'
            mock_config.EBAY_REFRESH_TOKEN = 'refresh_123'
            mock_config.EBAY_SANDBOX_MODE = True
            
            mock_post.return_value.status_code = 200
            mock_post.return_value.raise_for_status.return_value = None
            
            api = eBayAPI()
            api._access_token = 'test_token'
            result = api.publish_listing('listing_123')
            
            assert result is True

    @patch('services.scryfall_api.requests.get')
    def test_validate_rest_access_success(self, mock_get):
        """Test live-access validator returns true for successful sell-api auth."""
        with patch('services.scryfall_api.Config') as mock_config:
            mock_config.EBAY_APP_ID = 'app_123'
            mock_config.EBAY_DEV_ID = 'dev_123'
            mock_config.EBAY_USER_TOKEN = 'user_token_123'
            mock_config.EBAY_CLIENT_ID = 'client_123'
            mock_config.EBAY_CLIENT_SECRET = 'secret_123'
            mock_config.EBAY_REFRESH_TOKEN = 'refresh_123'
            mock_config.EBAY_SANDBOX_MODE = True

            mock_get.return_value.status_code = 200

            api = eBayAPI()
            assert api.validate_rest_access() is True
            assert api._last_auth_status == 200


# ========================
# MANABOX IMPORT TESTS
# ========================

class TestManaboxImport:
    """Tests for CSV import functionality"""
    
    def create_test_csv(self, data=None):
        """Helper to create test CSV"""
        if data is None:
            data = {
                'Name': ['Path to Exile'],
                'Set code': ['SLD'],
                'Set name': ['Secret Lair Drop'],
                'Collector number': ['226'],
                'Foil': ['normal'],
                'Rarity': ['rare'],
                'Quantity': [1],
                'ManaBox ID': ['64698'],
                'Scryfall ID': ['4e2fe951-4820-4555-8cee-621c66ed8620'],
                'Purchase price': [15.27],
                'Condition': ['near_mint'],
                'Language': ['en'],
            }
        df = pd.DataFrame(data)
        csv_buffer = BytesIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        return csv_buffer
    
    def test_import_multiple_cards(self, test_db):
        """Test importing multiple cards"""
        data = {
            'Name': ['Card 1', 'Card 2', 'Card 3'],
            'Set code': ['SET1', 'SET2', 'SET3'],
            'Set name': ['Set 1', 'Set 2', 'Set 3'],
            'Collector number': ['1', '2', '3'],
            'Foil': ['normal', 'foil', 'normal'],
            'Rarity': ['common', 'rare', 'uncommon'],
            'Quantity': [1, 2, 3],
            'ManaBox ID': ['id1', 'id2', 'id3'],
            'Scryfall ID': ['sf1', 'sf2', 'sf3'],
            'Purchase price': [1.0, 5.0, 2.0],
            'Condition': ['good', 'near_mint', 'lightly_played'],
            'Language': ['en', 'en', 'en'],
        }
        csv_file = self.create_test_csv(data)
        result = import_csv(test_db, csv_file)
        
        assert result['added'] == 3
        assert result['updated'] == 0
        assert result['skipped'] == 0
        
        cards = test_db.query(Card).all()
        assert len(cards) == 3
        assert cards[0].foil == False
        assert cards[1].foil == True
    
    def test_import_handles_duplicate_scryfall_ids(self, test_db):
        """Test that duplicate scryfall IDs are updated instead of created"""
        # First import
        data1 = {
            'Name': ['Card A'],
            'Set code': ['SET1'],
            'Set name': ['Set 1'],
            'Collector number': ['1'],
            'Foil': ['normal'],
            'Rarity': ['common'],
            'Quantity': [1],
            'ManaBox ID': ['id1'],
            'Scryfall ID': ['sf_duplicate'],
            'Purchase price': [1.0],
            'Condition': ['good'],
            'Language': ['en'],
        }
        csv_file1 = self.create_test_csv(data1)
        result1 = import_csv(test_db, csv_file1)
        assert result1['added'] == 1
        
        # Second import with same scryfall ID but different quantity
        data2 = {
            'Name': ['Card A'],
            'Set code': ['SET1'],
            'Set name': ['Set 1'],
            'Collector number': ['1'],
            'Foil': ['normal'],
            'Rarity': ['common'],
            'Quantity': [5],
            'ManaBox ID': ['id1'],
            'Scryfall ID': ['sf_duplicate'],
            'Purchase price': [1.0],
            'Condition': ['near_mint'],
            'Language': ['en'],
        }
        csv_file2 = self.create_test_csv(data2)
        result2 = import_csv(test_db, csv_file2)
        
        assert result2['added'] == 0
        assert result2['updated'] == 1
        
        cards = test_db.query(Card).all()
        assert len(cards) == 1
        assert cards[0].quantity == 5
        assert cards[0].condition == 'near_mint'
    
    def test_import_with_multiple_foil_formats(self, test_db):
        """Test import correctly handles various foil formats"""
        data = {
            'Name': ['Card 1', 'Card 2', 'Card 3', 'Card 4'],
            'Set code': ['S1', 'S2', 'S3', 'S4'],
            'Set name': ['S1', 'S2', 'S3', 'S4'],
            'Collector number': ['1', '2', '3', '4'],
            'Foil': ['foil', 'normal', 'Foil', 'FOIL'],
            'Rarity': ['c', 'c', 'c', 'c'],
            'Quantity': [1, 1, 1, 1],
            'ManaBox ID': ['i1', 'i2', 'i3', 'i4'],
            'Scryfall ID': ['sf1', 'sf2', 'sf3', 'sf4'],
            'Purchase price': [0, 0, 0, 0],
            'Condition': ['g', 'g', 'g', 'g'],
            'Language': ['en', 'en', 'en', 'en'],
        }
        csv_file = self.create_test_csv(data)
        result = import_csv(test_db, csv_file)
        
        cards = test_db.query(Card).all()
        assert cards[0].foil == True
        assert cards[1].foil == False
        assert cards[2].foil == True
        assert cards[3].foil == True


# ========================
# LOCATION ENGINE TESTS
# ========================

class TestLocationEngine:
    """Tests for location assignment logic"""
    
    def test_assign_location_distributed_across_boxes(self, test_db):
        """Test cards distributed correctly across multiple boxes"""
        # Set small capacity for testing
        from config import Config
        original_capacity = Config.BOX_CAPACITY
        Config.BOX_CAPACITY = 3
        
        try:
            cards = [
                Card(scryfall_id=f'sf{i}', name=f'Card {i}', set_code=f'S{i}', 
                     set_name=f'Set {i}', collector_number=str(i), quantity=1)
                for i in range(10)
            ]
            
            for card in cards:
                assign_location(test_db, card)
            
            boxes = test_db.query(Box).all()
            assert len(boxes) == 4  # 10 cards / 3 capacity = 4 boxes
            assert boxes[0].current_count == 3
            assert boxes[1].current_count == 3
            assert boxes[2].current_count == 3
            assert boxes[3].current_count == 1
        finally:
            Config.BOX_CAPACITY = original_capacity
    
    def test_location_codes_are_unique(self, test_db):
        """Test that all location codes are unique"""
        cards = [
            Card(scryfall_id=f'sf{i}', name=f'Card {i}', set_code=f'S{i}',
                 set_name=f'Set {i}', collector_number=str(i), quantity=1)
            for i in range(100)
        ]
        
        for card in cards:
            assign_location(test_db, card)
        
        location_codes = [card.location_code for card in cards]
        assert len(location_codes) == len(set(location_codes))
    
    def test_slot_numbers_sequential_per_box(self, test_db):
        """Test that slot numbers are sequential within each box"""
        from config import Config
        original_capacity = Config.BOX_CAPACITY
        Config.BOX_CAPACITY = 2
        
        try:
            cards = [
                Card(scryfall_id=f'sf{i}', name=f'Card {i}', set_code='S',
                     set_name='Set', collector_number=str(i), quantity=1)
                for i in range(6)
            ]
            
            for card in cards:
                assign_location(test_db, card)
            
            # Check box 1
            box1_cards = sorted([c for c in cards if c.box_number == 1], key=lambda x: x.slot_number)
            assert [c.slot_number for c in box1_cards] == [1, 2]
            
            # Check box 2
            box2_cards = sorted([c for c in cards if c.box_number == 2], key=lambda x: x.slot_number)
            assert [c.slot_number for c in box2_cards] == [1, 2]
            
            # Check box 3
            box3_cards = sorted([c for c in cards if c.box_number == 3], key=lambda x: x.slot_number)
            assert [c.slot_number for c in box3_cards] == [1, 2]
        finally:
            Config.BOX_CAPACITY = original_capacity


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
