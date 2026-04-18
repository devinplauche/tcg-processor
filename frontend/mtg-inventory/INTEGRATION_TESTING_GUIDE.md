# External Service Integration - Implementation Guide

## Quick Start: Running Tests

### 1. Unit Tests Only (Mocked APIs)
```bash
# Install dependencies
pip install -r requirements.txt

# Run unit tests (fast, no API calls needed)
pytest tests/ -v --tb=short

# Run with coverage
pytest tests/ --cov --cov-report=html
```

**Expected Result**: All 40+ tests passing in ~2 seconds

---

## Architecture: Mocks → Cassettes → Real APIs

```
┌─────────────────────────────────────────────────────────────┐
│ Development Flow                                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Write Tests       2. Add Mocks       3. Record Real     │
│     (TDD)                (Fast)           (Cassettes)       │
│     ↓                    ↓                ↓                 │
│  test_*.py       @patch('requests')   vcrpy.use_cassette  │
│                                                             │
│  4. Integration      5. Production     6. Monitor         │
│     Tests            Deployment        Rate Limits        │
│     ↓                ↓                 ↓                   │
│  Real APIs      Real Endpoints     Tenacity + Circuit    │
│                                    Breaker               │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Unit Tests with Mocks (Current)

### What You Have ✅

**File**: `test_services.py` (18 tests)
- All API calls mocked with `@patch`
- No network required
- Fast (~1 second)
- Useful for CI/CD

**File**: `test_services_extended.py` (30+ tests)
- Edge cases, timeouts, malformed responses
- Rate limiter tests
- Circuit breaker tests
- Contract validation tests

### How Mocking Works

```python
# In test_services.py
@patch('services.scryfall_api.requests.get')
def test_get_card_by_id_success(self, mock_get):
    # Mock the response
    mock_get.return_value.json.return_value = {
        'id': 'card_id',
        'name': 'Test Card'
    }
    
    # Call the real function (with mocked requests)
    result = ScryfallAPI.get_card_by_id('card_id')
    
    # Verify it works
    assert result['name'] == 'Test Card'
```

### Running Unit Tests

```bash
# All unit tests
pytest test_services.py test_services_extended.py -v

# With coverage
pytest test_services.py --cov=services --cov-report=term-missing

# Specific test
pytest test_services.py::TestScryfallAPI::test_get_card_by_id_success -v
```

---

## Phase 2: Test Fixtures with VCR.py (Cassettes)

VCR.py records real HTTP interactions and replays them, giving you real API responses without making network calls.

### Why Use Cassettes?

✅ **Real response schemas** - Cassettes contain actual API responses  
✅ **No API calls in CI** - Replay pre-recorded interactions  
✅ **Version tracking** - See API changes over time  
✅ **Offline testing** - No internet required  

### How It Works

```
First run (--record-cassettes):
  Test → Real API → Record response → cassette.yaml

Subsequent runs:
  Test → cassette.yaml (replay) → Verify logic
```

### Setting Up VCR Cassettes

1. **Create cassettes directory**:
```bash
mkdir tests/fixtures/cassettes
```

2. **Install vcrpy**:
```bash
pip install vcrpy
```

3. **Create conftest.py fixtures** (already done):
```python
# conftest.py
import vcr

scryfall_cassette = vcr.VCR(
    cassette_library_dir='tests/fixtures/cassettes',
    filter_headers=['Authorization'],  # Don't record auth headers
    record_mode='none',  # Don't make real requests unless --record-cassettes
)
```

4. **Use in tests**:
```python
@scryfall_cassette.use_cassette('scryfall_get_card.yaml')
def test_get_card_with_cassette():
    result = ScryfallAPI.get_card_by_id('4e2fe951-4820...')
    assert result['name'] == 'Path to Exile'
```

### Recording New Cassettes

```bash
# Record cassettes for Scryfall (makes real API calls)
pytest tests/ --record-cassettes -v -k "scryfall"

# Only records responses you're testing
# Creates: tests/fixtures/cassettes/scryfall_*.yaml
```

### Cassette File Structure

```yaml
# tests/fixtures/cassettes/scryfall_get_card.yaml
interactions:
- request:
    body: null
    headers: {}
    method: GET
    uri: https://api.scryfall.com/cards/4e2fe951-4820...
  response:
    status:
      code: 200
      message: OK
    headers: {}
    body:
      string: '{"id":"4e2fe951...","name":"Path to Exile",...}'
version: 1
```

---

## Phase 3: Integration Tests (Real APIs)

### Prerequisites

#### For Scryfall (Free ✅)
```bash
# No authentication needed!
# Just need internet connection
```

#### For TCGPlayer (Requires Credentials)
1. Create developer account at https://tcgplayer.com/api
2. Get API key and secret
3. Add to `.env`:
```env
TCGPLAYER_API_KEY=your_key_here
TCGPLAYER_API_SECRET=your_secret_here
```

#### For eBay (Requires OAuth)
1. Create developer account at https://developer.ebay.com
2. Create an application
3. Get credentials from sandbox
4. Add to `.env`:
```env
EBAY_CLIENT_ID=your_client_id
EBAY_CLIENT_SECRET=your_client_secret
EBAY_REFRESH_TOKEN=your_refresh_token
EBAY_SANDBOX_MODE=true  # Always true for testing
```

#### For Google Drive (Future)
```env
GOOGLE_DRIVE_CREDENTIALS_JSON=/path/to/credentials.json
GOOGLE_DRIVE_TEST_FOLDER_ID=folder_id_here
```

### Running Integration Tests

```bash
# Setup: Add credentials to .env

# Run integration tests (uses real APIs)
pytest tests/integration/ --integration -v

# Run only Scryfall integration (no credentials needed)
pytest tests/integration/test_scryfall_integration.py --integration -v

# Run only TCGPlayer (requires credentials)
pytest tests/integration/test_tcgplayer_integration.py --integration -v

# Record new cassettes for integration tests
pytest tests/integration/ --record-cassettes --integration -v
```

### Integration Test Example

```python
# tests/integration/test_scryfall_integration.py
@pytest.mark.integration
def test_scryfall_production_api():
    """Real API call to Scryfall (no mocking)"""
    api = ScryfallAPI()
    
    # Call real API
    result = api.get_card_by_id('4e2fe951-4820-4555-8cee-621c66ed8620')
    
    # Verify response matches contract
    is_valid, errors = ScryfallCardContract.validate(result)
    assert is_valid, f"Contract violation: {errors}"
    
    # Verify specific fields
    assert result['name'] == 'Path to Exile'
    assert isinstance(result['prices'], dict)
```

---

## Phase 4: Rate Limiting & Resilience

### Rate Limiter Usage

```python
from services.scryfall_api import ScryfallAPI
from services_rate_limiter import SCRYFALL_LIMITER

# API automatically rate-limits in production
def fetch_many_cards(card_ids):
    results = []
    for card_id in card_ids:
        SCRYFALL_LIMITER.wait_if_needed()  # Respects 10 req/s limit
        result = ScryfallAPI.get_card_by_id(card_id)
        results.append(result)
    return results

# Usage
cards = fetch_many_cards(['id1', 'id2', 'id3'])
```

### Retry Logic with Tenacity

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import requests

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.Timeout)
)
def fetch_with_retry(card_id):
    return ScryfallAPI.get_card_by_id(card_id)

# Will retry up to 3 times with exponential backoff
```

### Circuit Breaker Pattern

```python
from services_rate_limiter import CircuitBreaker

tcgplayer_breaker = CircuitBreaker(
    failure_threshold=3,  # Open after 3 failures
    recovery_timeout=120,  # Try again after 2 minutes
)

def get_pricing_safe(product_id):
    if not tcgplayer_breaker.is_available():
        return None  # Service is down, use cache
    
    try:
        api = TCGPlayerAPI()
        result = api.get_pricing(product_id)
        tcgplayer_breaker.record_success()
        return result
    except Exception as e:
        tcgplayer_breaker.record_failure()
        return None
```

---

## Phase 5: CI/CD Pipeline Setup

### GitHub Actions Workflow

Create `.github/workflows/tests.yml`:

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run unit tests (mocked)
        run: pytest test_services.py test_services_extended.py -v
      
      - name: Run E2E tests (mocked)
        run: pytest test_e2e.py -v
      
      - name: Coverage report
        run: pytest --cov=services --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  integration-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run integration tests
        env:
          TCGPLAYER_API_KEY: ${{ secrets.TCGPLAYER_API_KEY }}
          TCGPLAYER_API_SECRET: ${{ secrets.TCGPLAYER_API_SECRET }}
          EBAY_CLIENT_ID: ${{ secrets.EBAY_CLIENT_ID }}
          EBAY_CLIENT_SECRET: ${{ secrets.EBAY_CLIENT_SECRET }}
          EBAY_REFRESH_TOKEN: ${{ secrets.EBAY_REFRESH_TOKEN }}
        run: pytest tests/integration/ --integration -v
```

**To Add Secrets to GitHub**:
1. Go to repo → Settings → Secrets and variables → Actions
2. Add each secret (TCGPLAYER_API_KEY, etc.)

---

## Contract Testing

### What It Is

Contract testing verifies that API responses match the expected structure (contract).

### Example

```python
from tests_framework_contracts import ScryfallCardContract

def test_scryfall_card_contract():
    """Verify real API response matches contract"""
    api = ScryfallAPI()
    response = api.get_card_by_id('4e2fe951-4820...')
    
    # Check it matches contract
    is_valid, errors = ScryfallCardContract.validate(response)
    
    assert is_valid, f"Contract violations: {errors}"
```

### Contracts Defined

✅ ScryfallCardContract - Card lookup response  
✅ ScryfallSearchContract - Card search response  
✅ TCGPlayerAuthContract - Authentication response  
✅ TCGPlayerPricingContract - Pricing response  
✅ eBayAccessTokenContract - OAuth token  
✅ eBayListingContract - Listing creation response  

---

## Troubleshooting

### Problem: "Import Error: No module named 'vcrpy'"

**Solution**:
```bash
pip install vcrpy
```

### Problem: "API rate limit exceeded"

**Solution**:
```python
# Use rate limiter
from services_rate_limiter import SCRYFALL_LIMITER

SCRYFALL_LIMITER.wait_if_needed()
api.call()  # Now safe
```

### Problem: "401 Unauthorized" from TCGPlayer

**Solution**:
1. Verify credentials in `.env`
2. Token may have expired - regenerate in developer portal
3. Check IP is not blocked (contact support)

### Problem: Tests pass locally but fail in CI

**Solution**:
1. Verify all environment variables are in GitHub Secrets
2. Use cassettes instead of real API calls in CI
3. Check file permissions (cassettes must be readable)

---

## Testing Checklist

### Before Production

- [ ] All unit tests passing (40+ tests)
- [ ] All integration tests passing (optional)
- [ ] Contract validation passes
- [ ] Rate limits respected
- [ ] Error handling covers edge cases
- [ ] Cassettes recorded for all API calls
- [ ] CI/CD pipeline green
- [ ] Documentation complete
- [ ] API credentials stored securely
- [ ] Load testing with 1000+ cards

### Monthly

- [ ] Review rate limit statistics
- [ ] Check for API deprecations
- [ ] Update cassettes if needed
- [ ] Monitor error rates
- [ ] Review circuit breaker logs

---

## Next Steps

1. **Run existing tests**: `pytest test_services.py -v`
2. **Record cassettes**: `pytest tests/ --record-cassettes` (optional)
3. **Add integration tests**: `pytest tests/integration/ --integration`
4. **Monitor production**: Set up logging and alerting
5. **Build monitoring dashboard**: Track API health

---

## References

- **Scryfall API**: https://scryfall.com/docs/api
- **TCGPlayer API**: https://docs.tcgplayer.com/
- **eBay API**: https://developer.ebay.com/docs
- **VCR.py**: https://vcrpy.readthedocs.io/
- **Tenacity**: https://tenacity.readthedocs.io/
- **Pytest**: https://docs.pytest.org/

