"""
Extended service tests - Edge cases, timeouts, rate limits, and contract validation

These tests cover:
- Timeout handling
- Malformed responses
- Rate limiting behavior
- Circuit breaker functionality
- Contract validation
- Edge cases (empty responses, missing fields, etc.)
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import Mock, patch, MagicMock, call
import requests

from services.scryfall_api import ScryfallAPI, TCGPlayerAPI, eBayAPI
from services_rate_limiter import (
    RateLimiter, CircuitBreaker, SCRYFALL_LIMITER,
    TCGPLAYER_LIMITER, apply_rate_limit
)
from tests_framework_contracts import (
    ScryfallCardContract, TCGPlayerPricingContract,
    eBayAccessTokenContract
)


# ========================
# TIMEOUT TESTS
# ========================

class TestTimeoutHandling:
    """Tests for handling API timeouts"""
    
    @patch('services.scryfall_api.requests.get')
    def test_scryfall_timeout_returns_none(self, mock_get):
        """Verify Scryfall timeout returns None gracefully"""
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        
        result = ScryfallAPI.get_card_by_id("test_id")
        
        assert result is None
    
    @patch('services.scryfall_api.requests.get')
    def test_scryfall_search_timeout_returns_empty(self, mock_get):
        """Verify Scryfall search timeout returns empty list"""
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")
        
        result = ScryfallAPI.search_cards("lightning bolt")
        
        assert result == []
    
    @patch('services.scryfall_api.requests.post')
    def test_tcgplayer_auth_timeout_returns_none(self, mock_post):
        """Verify TCGPlayer auth timeout returns None"""
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")
        
        with patch('services.scryfall_api.Config') as mock_config:
            mock_config.TCGPLAYER_API_KEY = 'key'
            mock_config.TCGPLAYER_API_SECRET = 'secret'
            
            api = TCGPlayerAPI()
            token = api.get_auth_token()
            
            assert token is None


# ========================
# MALFORMED RESPONSE TESTS
# ========================

class TestMalformedResponses:
    """Tests for handling invalid/malformed API responses"""
    
    @patch('services.scryfall_api.requests.get')
    def test_scryfall_invalid_json_returns_none(self, mock_get):
        """Handle non-JSON response from Scryfall"""
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response
        
        result = ScryfallAPI.get_card_by_id("test_id")
        
        assert result is None
    
    @patch('services.scryfall_api.requests.get')
    def test_scryfall_http_error_returns_none(self, mock_get):
        """Handle HTTP errors from Scryfall"""
        mock_get.side_effect = requests.exceptions.HTTPError("404 Not Found")
        
        result = ScryfallAPI.get_card_by_id("invalid_id")
        
        assert result is None
    
    @patch('services.scryfall_api.requests.post')
    def test_tcgplayer_failed_auth_returns_none(self, mock_post):
        """Handle authentication failure from TCGPlayer"""
        mock_post.return_value.json.return_value = {
            'success': False,
            'errors': ['Invalid credentials']
        }
        mock_post.return_value.raise_for_status.return_value = None
        
        with patch('services.scryfall_api.Config') as mock_config:
            mock_config.TCGPLAYER_API_KEY = 'bad_key'
            mock_config.TCGPLAYER_API_SECRET = 'bad_secret'
            
            api = TCGPlayerAPI()
            token = api.get_auth_token()
            
            assert token is None
    
    @patch('services.scryfall_api.requests.post')
    def test_tcgplayer_missing_token_in_response(self, mock_post):
        """Handle missing token field in successful response"""
        mock_post.return_value.json.return_value = {
            'success': True,
            'data': {}  # Missing 'token'
        }
        mock_post.return_value.raise_for_status.return_value = None
        
        with patch('services.scryfall_api.Config') as mock_config:
            mock_config.TCGPLAYER_API_KEY = 'key'
            mock_config.TCGPLAYER_API_SECRET = 'secret'
            
            api = TCGPlayerAPI()
            token = api.get_auth_token()
            
            assert token is None


# ========================
# EMPTY/EDGE CASE TESTS
# ========================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""
    
    @patch('services.scryfall_api.requests.get')
    def test_scryfall_empty_search_results(self, mock_get):
        """Handle empty search results gracefully"""
        mock_get.return_value.json.return_value = {'data': []}
        mock_get.return_value.raise_for_status.return_value = None
        
        result = ScryfallAPI.search_cards("nothingexistshereever")
        
        assert result == []
    
    @patch('services.scryfall_api.requests.get')
    def test_scryfall_response_missing_fields(self, mock_get):
        """Handle Scryfall response missing optional fields"""
        mock_get.return_value.json.return_value = {
            'id': 'test_id',
            'name': 'Test Card',
            # Missing type_line, prices, etc.
        }
        mock_get.return_value.raise_for_status.return_value = None
        
        result = ScryfallAPI.get_card_by_id('test_id')
        
        # Should still return the response (missing optional fields is OK)
        assert result is not None
        assert result['name'] == 'Test Card'
    
    @patch('services.scryfall_api.requests.get')
    def test_scryfall_null_prices(self, mock_get):
        """Handle null price fields from Scryfall"""
        mock_get.return_value.json.return_value = {
            'id': 'test_id',
            'name': 'Test Card',
            'type_line': 'Instant',
            'prices': {
                'usd': None,
                'eur': None,
                'usd_foil': 15.00,
            }
        }
        mock_get.return_value.raise_for_status.return_value = None
        
        result = ScryfallAPI.get_card_by_id('test_id')
        
        assert result is not None
        assert result['prices']['usd'] is None
        assert result['prices']['usd_foil'] == 15.00
    
    @patch('services.scryfall_api.requests.get')
    def test_scryfall_search_with_zero_limit(self, mock_get):
        """Handle limit=0 in search"""
        mock_get.return_value.json.return_value = {
            'data': [{'id': '1', 'name': 'Card'}]
        }
        mock_get.return_value.raise_for_status.return_value = None
        
        result = ScryfallAPI.search_cards('test', limit=0)
        
        # Should return empty list when limit is 0
        assert result == []
    
    @patch('services.scryfall_api.requests.get')
    def test_scryfall_search_very_large_limit(self, mock_get):
        """Handle very large limit values"""
        mock_get.return_value.json.return_value = {
            'data': [{'id': str(i), 'name': f'Card {i}'} for i in range(100)]
        }
        mock_get.return_value.raise_for_status.return_value = None
        
        result = ScryfallAPI.search_cards('test', limit=999999)
        
        # Should return all 100 cards, not error out
        assert len(result) == 100


# ========================
# RATE LIMITER TESTS
# ========================

class TestRateLimiter:
    """Tests for rate limiting functionality"""
    
    def test_rate_limiter_allows_calls_within_limit(self):
        """Rate limiter should allow calls within the limit"""
        limiter = RateLimiter(calls_per_second=10)
        
        # 10 calls per second = 100ms per call
        import time
        start = time.time()
        
        for _ in range(3):
            limiter.wait_if_needed()
        
        elapsed = time.time() - start
        
        # Should allow 3 calls in ~300ms without waiting too long
        assert elapsed < 1.0
    
    def test_rate_limiter_enforces_limit(self):
        """Rate limiter should slow down calls exceeding limit"""
        limiter = RateLimiter(calls_per_second=2)  # 500ms per call
        
        import time
        start = time.time()
        
        # First call should not wait
        limiter.wait_if_needed()
        
        # Second call should wait ~500ms
        limiter.wait_if_needed()
        
        elapsed = time.time() - start
        
        # Should have waited at least 400ms (accounting for overhead)
        assert elapsed >= 0.4
    
    def test_rate_limiter_reset(self):
        """Rate limiter should reset properly"""
        limiter = RateLimiter(calls_per_second=10)
        limiter.wait_if_needed()
        
        stats_before = limiter.get_stats()
        assert stats_before['total_calls'] == 1
        
        limiter.reset()
        
        stats_after = limiter.get_stats()
        assert stats_after['total_calls'] == 0
    
    def test_rate_limiter_thread_safety(self):
        """Rate limiter should be thread-safe"""
        import threading
        limiter = RateLimiter(calls_per_second=100)
        call_count = [0]
        
        def make_call():
            limiter.wait_if_needed()
            call_count[0] += 1
        
        threads = [threading.Thread(target=make_call) for _ in range(10)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert call_count[0] == 10


# ========================
# CIRCUIT BREAKER TESTS
# ========================

class TestCircuitBreaker:
    """Tests for circuit breaker functionality"""
    
    def test_circuit_breaker_starts_closed(self):
        """Circuit breaker should start in CLOSED state"""
        breaker = CircuitBreaker()
        
        assert breaker.state == CircuitBreaker.CLOSED
        assert breaker.is_available()
    
    def test_circuit_breaker_opens_on_failures(self):
        """Circuit breaker should open after threshold failures"""
        breaker = CircuitBreaker(failure_threshold=3)
        
        # Record 3 failures
        for _ in range(3):
            breaker.record_failure()
        
        assert breaker.state == CircuitBreaker.OPEN
        assert not breaker.is_available()
    
    def test_circuit_breaker_recovers_after_timeout(self):
        """Circuit breaker should attempt recovery after timeout"""
        import time
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=1  # 1 second
        )
        
        breaker.record_failure()
        assert breaker.state == CircuitBreaker.OPEN
        assert not breaker.is_available()
        
        # After 1+ second, should go to HALF_OPEN
        time.sleep(1.1)
        assert breaker.is_available()  # Allows test request
        assert breaker.state == CircuitBreaker.HALF_OPEN
    
    def test_circuit_breaker_closes_on_success(self):
        """Circuit breaker should close on successful call in HALF_OPEN"""
        breaker = CircuitBreaker(failure_threshold=1)
        
        breaker.record_failure()
        assert breaker.state == CircuitBreaker.OPEN
        
        # Simulate recovery by fast-forwarding and recording success
        breaker.recovery_timeout = 0  # No wait needed
        if breaker.is_available():
            breaker.record_success()
        
        assert breaker.state == CircuitBreaker.CLOSED


# ========================
# CONTRACT VALIDATION TESTS
# ========================

class TestContractValidation:
    """Tests for API contract validation"""
    
    def test_scryfall_card_contract_valid(self):
        """Valid Scryfall card should pass contract"""
        valid_card = {
            'id': 'test_id',
            'name': 'Test Card',
            'type_line': 'Instant',
            'prices': {'usd': 10.0},
        }
        
        is_valid, errors = ScryfallCardContract.validate(valid_card)
        
        assert is_valid
        assert errors == []
    
    def test_scryfall_card_contract_missing_required(self):
        """Card missing required field should fail contract"""
        invalid_card = {
            'id': 'test_id',
            # Missing 'name' and 'type_line'
        }
        
        is_valid, errors = ScryfallCardContract.validate(invalid_card)
        
        assert not is_valid
        assert len(errors) > 0
        assert any('name' in e for e in errors)
    
    def test_scryfall_card_contract_wrong_type(self):
        """Field with wrong type should fail contract"""
        invalid_card = {
            'id': 'test_id',
            'name': 'Test',
            'type_line': 'Instant',
            'prices': 'not_a_dict',  # Should be dict
        }
        
        is_valid, errors = ScryfallCardContract.validate(invalid_card)
        
        assert not is_valid
        assert any('prices' in e for e in errors)
    
    def test_tcgplayer_pricing_contract_valid(self):
        """Valid TCGPlayer pricing should pass contract"""
        valid_pricing = {
            'success': True,
            'data': {
                'productId': 12345,
                'lowestListing': {
                    'price': 10.50,
                }
            }
        }
        
        is_valid, errors = TCGPlayerPricingContract.validate(valid_pricing)
        
        assert is_valid
        assert errors == []


# ========================
# CONNECTION ERROR TESTS
# ========================

class TestConnectionErrors:
    """Tests for handling connection errors"""
    
    @patch('services.scryfall_api.requests.get')
    def test_scryfall_connection_error_returns_none(self, mock_get):
        """Connection error should return None"""
        mock_get.side_effect = requests.exceptions.ConnectionError("No internet")
        
        result = ScryfallAPI.get_card_by_id("test_id")
        
        assert result is None
    
    @patch('services.scryfall_api.requests.post')
    def test_tcgplayer_connection_error_returns_none(self, mock_post):
        """TCGPlayer connection error should return None"""
        mock_post.side_effect = requests.exceptions.ConnectionError("No internet")
        
        with patch('services.scryfall_api.Config') as mock_config:
            mock_config.TCGPLAYER_API_KEY = 'key'
            mock_config.TCGPLAYER_API_SECRET = 'secret'
            
            api = TCGPlayerAPI()
            token = api.get_auth_token()
            
            assert token is None


# ========================
# INTEGRATION RATE LIMIT + CONTRACT TESTS
# ========================

class TestIntegrationWithRateLimiting:
    """Integration tests combining rate limiting and API calls"""
    
    @patch('services.scryfall_api.requests.get')
    def test_scryfall_with_rate_limiter_contract(self, mock_get):
        """Verify rate-limited Scryfall calls match contract"""
        mock_get.return_value.json.return_value = {
            'id': 'test_id',
            'name': 'Test Card',
            'type_line': 'Creature',
        }
        mock_get.return_value.raise_for_status.return_value = None
        
        limiter = RateLimiter(calls_per_second=10)
        
        # Simulate rate-limited calls
        for _ in range(3):
            limiter.wait_if_needed()
            result = ScryfallAPI.get_card_by_id('test_id')
            is_valid, errors = ScryfallCardContract.validate(result)
            
            assert is_valid, f"Contract validation failed: {errors}"
