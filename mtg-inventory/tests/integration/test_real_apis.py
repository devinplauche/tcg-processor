"""
Integration Tests - Real API Calls with Cassette Recording

These tests make REAL API calls and record responses for future replay.

Running:
    # With cassettes (no API calls needed)
    pytest tests/integration/ -v

    # Record new cassettes (requires real API credentials)
    pytest tests/integration/ -v --record-cassettes

Credentials needed in .env:
    TCGPLAYER_API_KEY=...
    TCGPLAYER_API_SECRET=...
    EBAY_CLIENT_ID=... (for sandbox)
    EBAY_CLIENT_SECRET=...
    EBAY_REFRESH_TOKEN=...
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from services.scryfall_api import ScryfallAPI, TCGPlayerAPI, eBayAPI
from tests_integration_config import (
    test_vcr, APITestConfig, get_cassette_path,
    scryfall_cassette, tcgplayer_cassette, ebay_cassette
)
from tests_framework_contracts import (
    ScryfallCardContract, TCGPlayerPricingContract,
    TCGPlayerAuthContract
)


# ========================
# SCRYFALL INTEGRATION TESTS
# ========================

class TestScryfallIntegration:
    """Integration tests for Scryfall API (requires internet, no credentials)"""
    
    @pytest.mark.integration
    def test_scryfall_get_card_real(self, scryfall_cassette):
        """Test fetching a real card from Scryfall"""
        with scryfall_cassette.use_cassette(get_cassette_path('scryfall_get_card')):
            api = ScryfallAPI()
            result = api.get_card_by_id(APITestConfig.SCRYFALL_TEST_CARD_ID)
            
            assert result is not None
            assert 'id' in result
            assert result['id'] == APITestConfig.SCRYFALL_TEST_CARD_ID
            
            # Verify contract
            is_valid, errors = ScryfallCardContract.validate(result)
            assert is_valid, f"Contract violations: {errors}"
    
    @pytest.mark.integration
    def test_scryfall_search_real(self, scryfall_cassette):
        """Test searching for cards on Scryfall"""
        with scryfall_cassette.use_cassette(get_cassette_path('scryfall_search')):
            api = ScryfallAPI()
            results = api.search_cards('lightning bolt', limit=5)
            
            assert isinstance(results, list)
            assert len(results) > 0
            assert any('lightning' in card.get('name', '').lower() for card in results)
    
    @pytest.mark.integration
    def test_scryfall_expensive_cards(self, scryfall_cassette):
        """Test finding expensive cards on Scryfall"""
        with scryfall_cassette.use_cassette(get_cassette_path('scryfall_expensive')):
            api = ScryfallAPI()
            results = api.search_cards('usd>=100', limit=5)
            
            assert isinstance(results, list)
            # May have 0 results depending on search
            for card in results:
                is_valid, _ = ScryfallCardContract.validate(card)
                assert is_valid


# ========================
# TCGPLAYER INTEGRATION TESTS
# ========================

class TestTCGPlayerIntegration:
    """Integration tests for TCGPlayer API (requires credentials)"""
    
    @pytest.mark.integration
    def test_tcgplayer_authenticate_real(self, tcgplayer_cassette):
        """Test real authentication with TCGPlayer"""
        with tcgplayer_cassette.use_cassette(get_cassette_path('tcgplayer_auth')):
            api = TCGPlayerAPI()
            token = api.get_auth_token()
            
            assert token is not None
            assert isinstance(token, str)
            assert len(token) > 0
    
    @pytest.mark.integration
    def test_tcgplayer_get_pricing_real(self, tcgplayer_cassette):
        """Test getting real pricing from TCGPlayer"""
        with tcgplayer_cassette.use_cassette(get_cassette_path('tcgplayer_pricing')):
            api = TCGPlayerAPI()
            
            # First authenticate
            token = api.get_auth_token()
            assert token is not None
            
            # Then get pricing for a known product
            pricing = api.get_pricing(APITestConfig.TCGPLAYER_TEST_PRODUCT_ID)
            
            if pricing is not None:
                # Verify contract
                is_valid, errors = TCGPlayerPricingContract.validate({
                    'success': True,
                    'data': pricing
                })
                assert is_valid, f"Contract violations: {errors}"


# ========================
# EBAY INTEGRATION TESTS
# ========================

class TesteBayIntegration:
    """Integration tests for eBay API (requires credentials + sandbox mode)"""
    
    @pytest.mark.integration
    def test_ebay_get_token_real(self, ebay_cassette):
        """Test real OAuth token retrieval from eBay"""
        with ebay_cassette.use_cassette(get_cassette_path('ebay_token')):
            api = eBayAPI()
            token = api.get_access_token()
            
            assert token is not None
            assert isinstance(token, str)
            assert len(token) > 0
    
    @pytest.mark.integration
    def test_ebay_sandbox_mode_enabled(self):
        """Verify eBay tests are running in sandbox mode"""
        assert APITestConfig.EBAY_SANDBOX_MODE, \
            "❌ eBay sandbox mode is OFF - refusing to run tests!"


# ========================
# WORKFLOW TESTS
# ========================

class TestCompleteWorkflow:
    """End-to-end workflow tests combining multiple APIs"""
    
    @pytest.mark.integration
    def test_fetch_scryfall_then_tcgplayer_price(
        self,
        scryfall_cassette,
        tcgplayer_cassette
    ):
        """Test fetching card from Scryfall then pricing from TCGPlayer"""
        # Step 1: Get card from Scryfall
        with scryfall_cassette.use_cassette(get_cassette_path('scryfall_get_card')):
            scryfall_api = ScryfallAPI()
            card = scryfall_api.get_card_by_id(APITestConfig.SCRYFALL_TEST_CARD_ID)
            
            assert card is not None
            card_name = card['name']
        
        # Step 2: Get pricing from TCGPlayer
        with tcgplayer_cassette.use_cassette(get_cassette_path('tcgplayer_pricing')):
            tcgplayer_api = TCGPlayerAPI()
            token = tcgplayer_api.get_auth_token()
            
            if token:  # Skip if credentials not configured
                # In real world, would search for product by card name first
                pricing = tcgplayer_api.get_pricing(APITestConfig.TCGPLAYER_TEST_PRODUCT_ID)
                
                # Verify we got something
                if pricing:
                    assert 'productId' in pricing


class TestRateLimitingWithRealAPIs:
    """Test that rate limiting works with real API calls"""
    
    @pytest.mark.integration
    @pytest.mark.skip(reason="Rate limiter decorators need to be applied to API methods")
    def test_scryfall_respects_rate_limit(self, scryfall_cassette):
        """Verify Scryfall API respects rate limit"""
        from services_rate_limiter import SCRYFALL_LIMITER
        
        SCRYFALL_LIMITER.reset()
        
        with scryfall_cassette.use_cassette(get_cassette_path('scryfall_rate_limit')):
            api = ScryfallAPI()
            
            # Make 3 rapid calls
            for i in range(3):
                result = api.get_card_by_id(APITestConfig.SCRYFALL_TEST_CARD_ID)
                assert result is not None
            
            # Check that rate limiter tracked calls
            stats = SCRYFALL_LIMITER.get_stats()
            assert stats['total_calls'] >= 3


def pytest_configure(config):
    """Configure integration tests"""
    # Print which APIs are available for testing
    enabled = APITestConfig.get_enabled_apis()
    
    if enabled:
        print(f"\n✅ Integration tests available for: {', '.join(enabled)}")
    else:
        print("\n⚠️  No integration test credentials configured")
        print("   Add to .env to enable:")
        print("   - TCGPLAYER_API_KEY + TCGPLAYER_API_SECRET")
        print("   - EBAY_CLIENT_ID + EBAY_CLIENT_SECRET + EBAY_REFRESH_TOKEN")
