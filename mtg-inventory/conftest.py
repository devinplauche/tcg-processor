"""
Pytest configuration and shared fixtures for all tests
"""
import pytest
import os
from unittest.mock import Mock, patch
from io import BytesIO
import pandas as pd

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as requiring real API credentials"
    )
    config.addinivalue_line(
        "markers", "vcr: mark test as using recorded cassettes"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow to run"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test with mocks"
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless --integration flag is passed"""
    if config.getoption("--integration"):
        # Run integration tests
        return
    
    skip_integration = pytest.mark.skip(
        reason="need --integration option to run"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


def pytest_addoption(parser):
    """Add custom command-line options"""
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="run integration tests (requires API credentials)"
    )
    parser.addoption(
        "--record-cassettes",
        action="store_true",
        default=False,
        help="record new VCR cassettes (real API calls)"
    )
    
    # Set VCR record mode based on flag
    if '--record-cassettes' in os.sys.argv:
        os.environ['VCR_RECORD_MODE'] = 'all'  # Record all interactions
    elif 'VCR_RECORD_MODE' not in os.environ:
        os.environ['VCR_RECORD_MODE'] = 'once'  # Default: use existing cassettes


@pytest.fixture(scope="session")
def test_db_factory():
    """Factory for creating test databases"""
    def create_test_db():
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(bind=engine)
        TestSession = sessionmaker(bind=engine, expire_on_commit=False)
        return TestSession, engine
    return create_test_db


@pytest.fixture
def test_db():
    """Create a fresh in-memory database for each test"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    db = TestSession()
    
    yield db
    
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_card_csv():
    """Generate a sample MTG card CSV for testing"""
    data = {
        'scryfall_id': [
            '4e2fe951-4820-4555-8cee-621c66ed8620',
            '9e3db3d4-8d16-44f7-a37b-480d9d0e8fee',
        ],
        'name': ['Path to Exile', 'Lightning Bolt'],
        'quantity': [1, 3],
        'manabox_id': [1.0, 1.0],
        'foil': ['normal', 'foil'],
        'condition': ['NM', 'LP'],
    }
    df = pd.DataFrame(data)
    
    # Convert to BytesIO
    csv_buffer = BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    
    return csv_buffer


@pytest.fixture
def api_response_templates():
    """Provide standard API response templates for mocking"""
    return {
        'scryfall_card': {
            'id': '4e2fe951-4820-4555-8cee-621c66ed8620',
            'name': 'Path to Exile',
            'type_line': 'Instant',
            'prices': {
                'usd': 15.99,
                'eur': 14.50,
                'eur_foil': None,
                'usd_foil': 25.50,
            },
            'image_uris': {
                'small': 'https://...',
                'normal': 'https://...',
            }
        },
        'ebay_access_token': {
            'access_token': 'test_access_token_abc123',
            'token_type': 'Bearer',
            'expires_in': 3600,
        },
        'ebay_listing': {
            'itemId': '123456789',
            'title': 'Test Card - NM',
            'price': 9.99,
            'status': 'ACTIVE',
        }
    }


@pytest.fixture
def mock_config():
    """Mock configuration with test values"""
    with patch('config.Config') as mock:
        mock.BOX_CAPACITY = 500
        mock.DATABASE_URL = 'sqlite:///:memory:'
        mock.FLASK_SECRET_KEY = 'test_secret'
        mock.BASE_URL = 'http://localhost:5000'
        
        # API Credentials (empty/test for mocking)
        mock.SCRYFALL_API = 'https://api.scryfall.com'
        mock.EBAY_CLIENT_ID = 'test_client_id'
        mock.EBAY_CLIENT_SECRET = 'test_client_secret'
        mock.EBAY_REFRESH_TOKEN = 'test_refresh_token'
        mock.EBAY_SANDBOX_MODE = True
        
        yield mock


@pytest.fixture
def request_timeout_exception():
    """Mock a request timeout exception"""
    import requests
    return requests.exceptions.Timeout("Connection timed out")


@pytest.fixture
def request_connection_exception():
    """Mock a connection error exception"""
    import requests
    return requests.exceptions.ConnectionError("Failed to connect")


@pytest.fixture
def malformed_json_response():
    """Mock a malformed JSON response"""
    from unittest.mock import Mock
    response = Mock()
    response.json.side_effect = ValueError("Invalid JSON")
    return response


@pytest.fixture
def rate_limit_response():
    """Mock a rate limit response (429)"""
    from unittest.mock import Mock
    response = Mock()
    response.status_code = 429
    response.headers = {'Retry-After': '60'}
    response.json.return_value = {'error': 'rate limit exceeded'}
    return response
