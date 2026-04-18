# TDD Quick Reference - Testing Checklist

## Before Starting Development

- [ ] Activated Python venv: `. .venv/Scripts/activate` (or on Windows: `.venv\Scripts\activate`)
- [ ] Installed dependencies: `pip install -r requirements.txt`
- [ ] Created `.env` file with API credentials (optional, for integration tests)

## Running Tests

### Unit Tests (Recommended - Always Use Mocks)
```bash
# All mocked tests
pytest test_services.py test_services_extended.py -v

# Just timeout/edge case tests
pytest test_services_extended.py::TestTimeoutHandling -v

# With coverage report
pytest test_services.py --cov=services --cov-report=html

# Quick summary
pytest test_services.py -q
```

### Integration Tests (Optional - Requires Real Credentials)
```bash
# Only if: TCGPLAYER_API_KEY and TCGPLAYER_API_SECRET in .env
pytest tests/integration/ --integration -v

# Only Scryfall (no credentials needed)
pytest tests/integration/test_scryfall_integration.py --integration -v
```

## Writing New Tests

### Template 1: Mock an API Call
```python
from unittest.mock import patch

@patch('services.scryfall_api.requests.get')
def test_my_api_call(self, mock_get):
    # Set up mock response
    mock_get.return_value.json.return_value = {
        'id': 'test_id',
        'name': 'Test Card'
    }
    mock_get.return_value.raise_for_status.return_value = None
    
    # Call the real function
    result = ScryfallAPI.get_card_by_id('test_id')
    
    # Verify it worked
    assert result['name'] == 'Test Card'
    mock_get.assert_called_once()
```

### Template 2: Test Error Handling
```python
@patch('services.scryfall_api.requests.get')
def test_api_timeout(self, mock_get):
    # Simulate timeout
    import requests
    mock_get.side_effect = requests.exceptions.Timeout("timeout")
    
    # Should return None gracefully
    result = ScryfallAPI.get_card_by_id('test_id')
    
    assert result is None
```

### Template 3: Test with Fixtures
```python
def test_with_test_db(self, test_db):
    """Use fixture to get fresh database"""
    # test_db is an in-memory SQLite session
    db = test_db
    db.add(Card(...))
    db.commit()
    
    assert db.query(Card).count() == 1
```

## Common Test Patterns

### Rate Limiter Testing
```python
from services_rate_limiter import RateLimiter

def test_rate_limit():
    limiter = RateLimiter(calls_per_second=2)
    
    # 3 calls - second one should wait
    limiter.wait_if_needed()
    limiter.wait_if_needed()  # Waits ~500ms
    
    stats = limiter.get_stats()
    assert stats['total_calls'] == 2
```

### Circuit Breaker Testing
```python
from services_rate_limiter import CircuitBreaker

def test_circuit_breaker():
    breaker = CircuitBreaker(failure_threshold=3)
    
    # Record 3 failures
    for _ in range(3):
        breaker.record_failure()
    
    # Circuit is now open
    assert not breaker.is_available()
```

### Contract Validation
```python
from tests_framework_contracts import ScryfallCardContract

def test_contract(self):
    response = {...}  # API response
    
    is_valid, errors = ScryfallCardContract.validate(response)
    
    assert is_valid, f"Violations: {errors}"
```

## Debugging Failed Tests

### Problem: "Module not found"
```bash
pip install -r requirements.txt
```

### Problem: "Test timeout during import"
```bash
# Check if there's a stray vcrpy cassette being loaded
# or a real API call in conftest.py
```

### Problem: "Mock not being called"
```python
# Verify the patch path matches the import
@patch('services.scryfall_api.requests.get')  # Correct
# NOT: @patch('requests.get')  # Wrong - patches global requests

# Verify mock is set up before calling function
mock_get.return_value.json.return_value = {...}
mock_get.return_value.raise_for_status.return_value = None

# Then call the function
result = ScryfallAPI.get_card_by_id(...)

# Verify it was called
mock_get.assert_called_once()
```

## Best Practices

### Do ✅
- Mock all external API calls
- Test error conditions (timeouts, malformed data, etc.)
- Use fixtures for test data
- Name tests descriptively: `test_get_card_by_id_success`
- Keep unit tests fast (< 1 second per test)
- Validate contracts before production

### Don't ❌
- Make real API calls in unit tests
- Hardcode credentials in test files
- Share test databases between test functions
- Use `time.sleep()` in tests (it's slow!)
- Test implementation details, test behavior

## Test Organization

```
mtg-inventory/
├── test_services.py              # 18 original tests
├── test_services_extended.py     # 27 new tests
├── test_e2e.py                   # 12 end-to-end tests
├── test_import.py                # 12 import tests
├── conftest.py                   # Fixtures & config
├── tests/
│   ├── unit/
│   │   └── test_*.py            # Unit tests (mock only)
│   ├── integration/
│   │   └── test_*.py            # Integration tests (real APIs)
│   └── fixtures/
│       └── cassettes/
│           └── *.yaml           # Recorded API responses
```

## Running All Tests

### Local Development
```bash
# All tests with mocks
pytest . -v --tb=short

# Coverage report
pytest . --cov --cov-report=html
# Opens in: htmlcov/index.html
```

### Before Committing
```bash
# Check that all mocked tests pass
pytest test_services.py test_services_extended.py -v

# Verify coverage
pytest --cov=services --cov-report=term-missing
```

### In CI/CD Pipeline
```bash
# Only mocked tests (no external dependencies)
pytest unit/ -v --tb=short

# Integration tests run separately on main branch
# (requires credentials in secrets)
```

## API Response Mocking

### Scryfall Card
```python
{
    'id': 'card-id',
    'name': 'Card Name',
    'type_line': 'Instant',
    'prices': {
        'usd': 10.00,
        'usd_foil': 15.00,
    }
}
```

### TCGPlayer Token
```python
{
    'success': True,
    'data': {
        'token': 'eyJhbGc...',
        'user_id': 12345,
    }
}
```

### TCGPlayer Pricing
```python
{
    'success': True,
    'data': {
        'productId': 12345,
        'lowestListing': {
            'price': 8.50,
            'quantity': 10,
        },
        'average': 10.25,
    }
}
```

### eBay Token
```python
{
    'access_token': 'v^1ABC...',
    'token_type': 'Bearer',
    'expires_in': 3600,
}
```

## Helpful pytest Flags

```bash
pytest -v              # Verbose output
pytest -q              # Quiet output
pytest --tb=short      # Short traceback
pytest --tb=long       # Long traceback
pytest -k "keyword"    # Run tests matching keyword
pytest -x              # Stop on first failure
pytest --lf            # Run last failed
pytest --maxfail=3     # Stop after 3 failures
pytest --durations=10  # Show 10 slowest tests
pytest --co            # Collect tests (don't run)
pytest --markers       # Show all markers
```

## Monitoring Production APIs

```python
from services_rate_limiter import SCRYFALL_LIMITER

# Check rate limiter stats
stats = SCRYFALL_LIMITER.get_stats()
print(f"Total calls: {stats['total_calls']}")
print(f"Times waited: {stats['total_waits']}")
print(f"Avg wait per call: {stats['average_wait_per_call']:.3f}s")

# Check circuit breaker state
breaker_state = SCRYFALL_BREAKER.get_state()
print(f"State: {breaker_state['state']}")
print(f"Failures: {breaker_state['failure_count']}")
```

---

**Last Updated**: March 4, 2026  
**Test Suite**: 45 tests, 100% passing  
**Framework**: TDD with mocks and cassettes

