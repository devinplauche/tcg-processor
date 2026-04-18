"""
Integration Test Configuration

Sets up VCR cassettes and real API test fixtures.
Enables recording real API responses for CI/CD replay.
"""

import os
import vcr
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from models import Card


# VCR Configuration
CASSETTES_DIR = Path(__file__).parent / "tests" / "fixtures" / "cassettes"
CASSETTES_DIR.mkdir(parents=True, exist_ok=True)


def _scrub_request(request):
    """Remove sensitive data from recorded requests"""
    # Remove API keys from query strings
    if 'key=' in request.uri:
        request.uri = request.uri.split('&key=')[0]
    if 'secret=' in request.uri:
        request.uri = request.uri.split('&secret=')[0]
    
    # Remove auth headers
    if 'Authorization' in request.headers:
        request.headers['Authorization'] = 'REDACTED'
    
    return request


def _scrub_response(response):
    """Remove sensitive data from recorded responses"""
    # No sensitive data in responses typically, but keep consistent
    return response


# Create VCR instance with sensible defaults
test_vcr = vcr.VCR(
    cassette_library_dir=str(CASSETTES_DIR),
    
    # Record mode options:
    # 'once': Only record if cassette doesn't exist
    # 'new_episodes': Record new interactions to existing cassette
    # 'none': Only playback, fail if cassette missing
    # 'all': Record all interactions (overwrites)
    record_mode=os.getenv('VCR_RECORD_MODE', 'once'),
    
    # Match requests by method and URI (not body or headers)
    match_on=['method', 'scheme', 'host', 'port', 'path', 'query'],
    
    # Filter sensitive data
    before_record_request=_scrub_request,
    before_record_response=_scrub_response,
    
    # Other options
    decode_compressed_response=True,
    filter_headers=['Authorization', 'Authorization', 'X-API-Key'],
)


def get_cassette_path(name: str) -> str:
    """Get full path to a cassette file"""
    return str(CASSETTES_DIR / f"{name}.yaml")


class APITestConfig:
    """Configuration for API integration tests"""
    
    # Scryfall (no auth needed, safe for CI/CD)
    SCRYFALL_ENABLED = True
    SCRYFALL_TEST_CARD_ID = "4e2fe951-4820-4555-8cee-621c66ed8620"  # Path to Exile
    
    # TCGPlayer (requires credentials)
    TCGPLAYER_ENABLED = bool(
        os.getenv('TCGPLAYER_API_KEY') and 
        os.getenv('TCGPLAYER_API_SECRET')
    )
    TCGPLAYER_TEST_PRODUCT_ID = 123456  # Example product
    
    # eBay (requires credentials, uses sandbox)
    EBAY_ENABLED = bool(
        os.getenv('EBAY_CLIENT_ID') and
        os.getenv('EBAY_CLIENT_SECRET') and
        os.getenv('EBAY_REFRESH_TOKEN')
    )
    EBAY_SANDBOX_MODE = os.getenv('EBAY_SANDBOX_MODE', 'true').lower() in ('true', '1', 't')
    
    # Google Drive (future feature)
    GOOGLE_DRIVE_ENABLED = bool(os.getenv('GOOGLE_DRIVE_CREDENTIALS_JSON'))
    
    @staticmethod
    def get_enabled_apis() -> list[str]:
        """Get list of enabled APIs"""
        enabled = []
        if APITestConfig.SCRYFALL_ENABLED:
            enabled.append('scryfall')
        if APITestConfig.TCGPLAYER_ENABLED:
            enabled.append('tcgplayer')
        if APITestConfig.EBAY_ENABLED:
            enabled.append('ebay')
        if APITestConfig.GOOGLE_DRIVE_ENABLED:
            enabled.append('google_drive')
        return enabled
    
    @staticmethod
    def print_config():
        """Print integration test configuration"""
        print("\n" + "="*60)
        print("INTEGRATION TEST CONFIGURATION")
        print("="*60)
        print(f"Scryfall:      {'✅ ENABLED' if APITestConfig.SCRYFALL_ENABLED else '❌ DISABLED'}")
        print(f"TCGPlayer:     {'✅ ENABLED' if APITestConfig.TCGPLAYER_ENABLED else '❌ DISABLED (missing credentials)'}")
        print(f"eBay:          {'✅ ENABLED' if APITestConfig.EBAY_ENABLED else '❌ DISABLED (missing credentials)'}")
        print(f"  Sandbox:     {'✅ ON' if APITestConfig.EBAY_SANDBOX_MODE else '❌ OFF (PRODUCTION!)'}")
        print(f"Google Drive:  {'✅ ENABLED' if APITestConfig.GOOGLE_DRIVE_ENABLED else '❌ DISABLED (future feature)'}")
        print(f"VCR Mode:      {os.getenv('VCR_RECORD_MODE', 'once')}")
        print(f"Cassettes:     {CASSETTES_DIR}")
        print("="*60 + "\n")


@pytest.fixture(scope="session")
def persistent_test_db():
    """
    Use the persistent test database (test_data.db)
    
    Database should be initialized with: python setup_test_data.py
    """
    db_path = "test_data.db"
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"\n❌ Test database not found: {db_path}\n\n"
            f"   Initialize with: python setup_test_data.py\n\n"
            f"   This creates a persistent test database with realistic "
            f"MTG card data (only needs to run once)."
        )
    
    engine = create_engine(f"sqlite:///{db_path}")
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    
    yield session
    
    session.close()


@pytest.fixture
def scryfall_cassette(request):
    """
    Use VCR cassette for Scryfall API tests
    
    Usage:
        def test_with_scryfall(scryfall_cassette):
            with scryfall_cassette.use_cassette('scryfall_get_card.yaml'):
                result = ScryfallAPI.get_card_by_id(...)
    """
    if not APITestConfig.SCRYFALL_ENABLED:
        pytest.skip("Scryfall API not enabled")
    
    return test_vcr


@pytest.fixture
def tcgplayer_cassette(request):
    """Use VCR cassette for TCGPlayer API tests"""
    if not APITestConfig.TCGPLAYER_ENABLED:
        pytest.skip("TCGPlayer API not enabled (missing credentials)")
    
    return test_vcr


@pytest.fixture
def ebay_cassette(request):
    """Use VCR cassette for eBay API tests"""
    if not APITestConfig.EBAY_ENABLED:
        pytest.skip("eBay API not enabled (missing credentials)")
    
    if not APITestConfig.EBAY_SANDBOX_MODE:
        pytest.skip("eBay sandbox mode is OFF - refusing to run tests!")
    
    return test_vcr


# Print config when tests start
def pytest_configure(config):
    """Print integration test configuration"""
    APITestConfig.print_config()
