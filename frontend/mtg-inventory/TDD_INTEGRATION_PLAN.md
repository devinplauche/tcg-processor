# TDD Integration Plan for External Services

## Overview

This document outlines the Test-Driven Development (TDD) strategy for integrating with external services (Scryfall, TCGPlayer, eBay, Google Drive). The approach follows the principle: **Start with mocks → Build tests → Add real integrations → Verify and document**.

---

## Current State

### ✅ What We Have
- **Unit tests with mocks** (18 tests in `test_services.py`)
- **E2E tests with mocks** (12 tests in `test_e2e.py`)
- **Service implementations** (scryfall_api.py, tcgplayer_api.py, ebay_api.py)
- **Config-driven credentials** (environment variables)
- **Graceful error handling** (None returns on failure)

### ❌ What We Need
- **Integration tests** with real API calls
- **Test fixtures/cassettes** for recorded API responses
- **Environment-based test selection** (unit vs integration)
- **API response verification** (contract testing)
- **Rate limit handling** for production use
- **Sandbox/staging credentials** for testing

---

## Phase 1: Expand Mock Tests (In Progress)

### Goals
- Ensure 100% mock coverage before real integration
- Document expected API contracts
- Create test fixtures for all response types

### Tasks
1. ✅ **Basic happy path tests** (already done)
2. ✅ **Error handling tests** (already done)
3. ⬜ **Edge case tests** (add malformed responses, timeouts)
4. ⬜ **Rate limit tests** (mock rate limit headers)
5. ⬜ **Response validation** (verify schema conformance)

### Test Coverage Matrix

```
Service          | Unit Tests | E2E Tests | Integration | Status
-----------------|------------|-----------|-------------|--------
ScryfallAPI      |     ✅ 5   |    ✅ 2   |      ⬜     | Ready
TCGPlayerAPI     |     ✅ 4   |    ✅ 2   |      ⬜     | Ready
eBayAPI          |     ✅ 3   |    ✅ 2   |      ⬜     | Ready
GoogleDriveAPI   |     ⬜ 0   |    ⬜ 0   |      ⬜     | Pending
CSV Import       |     ✅ 3   |    ✅ 1   |      ⬜     | Ready
Location Engine  |     ✅ 3   |    ✅ 3   |      ⬜     | Ready
Complete Flow    |     N/A    |    ✅ 2   |      ⬜     | Ready
```

---

## Phase 2: Test Fixture Management

### Strategy: VCR.py (Cassettes)

Use `vcrpy` to record real API responses and replay them in tests.

**Benefits:**
- No API calls during normal test runs (fast, reliable)
- Real response schemas in fixtures
- Easy to update when APIs change
- Supports multiple response scenarios

**Structure:**
```
tests/
  fixtures/
    cassettes/
      scryfall/
        get_card_by_id_success.yaml
        get_card_by_id_not_found.yaml
        search_cards.yaml
      tcgplayer/
        authenticate.yaml
        get_pricing.yaml
      ebay/
        create_listing.yaml
        publish_listing.yaml
```

### Implementation
1. Install `vcrpy`: `pip install vcrpy`
2. Create `conftest.py` with fixture decorators
3. Record initial cassettes with real API calls (one-time)
4. Use cassettes in all normal test runs

---

## Phase 3: Integration Tests (Real API Calls)

### Environment Configuration

Add new environment variables:
```bash
# Mock/Unit tests (default)
TEST_MODE=unit

# Integration tests with real APIs
TEST_MODE=integration

# Which services to test
TEST_SCRYFALL=true
TEST_TCGPLAYER=true    # Requires: TCGPLAYER_API_KEY + TCGPLAYER_API_SECRET
TEST_EBAY=true         # Requires: EBAY_CLIENT_ID + EBAY_CLIENT_SECRET + EBAY_REFRESH_TOKEN
TEST_GOOGLE_DRIVE=true # Requires: GOOGLE_DRIVE_CREDENTIALS_JSON
```

### Test Organization

```
tests/
  unit/
    test_services_mock.py         # 25 tests, mocked, ~1s
  integration/
    test_services_real.py         # 20 tests, real APIs, ~10s
    test_scryfall_integration.py  # 5 tests, Scryfall only
    test_tcgplayer_integration.py # 5 tests, TCGPlayer only
    test_ebay_integration.py      # 5 tests, eBay sandbox
    test_google_drive_integration.py # 5 tests, Google Drive
  e2e/
    test_workflows_mock.py        # 12 tests, mocked, ~2s
    test_workflows_real.py        # 8 tests, real APIs, ~15s
```

### Running Tests

```bash
# Unit tests only (fastest - uses mocks & cassettes)
pytest tests/unit/ -v

# Integration tests (requires credentials)
pytest tests/integration/ -v --integration

# All tests
pytest --integration

# Specific service
pytest tests/integration/test_scryfall_integration.py -v
```

---

## Phase 4: API Contract Testing

### What is Contract Testing?

Define expected API contract (schema, fields, types) and verify endpoints conform to it.

### Implementation Strategy

Create contract definitions:

```python
# tests/contracts.py

SCRYFALL_CARD_CONTRACT = {
    "required": ["id", "name", "type_line"],
    "optional": ["prices", "image_uris"],
    "types": {
        "id": str,
        "name": str,
        "prices": dict,
        "prices.usd": float,
    }
}

TCGPLAYER_PRICING_CONTRACT = {
    "required": ["productId", "lowPrice", "midPrice", "highPrice"],
    "types": {
        "productId": int,
        "lowPrice": float,
    }
}

EBAY_LISTING_CONTRACT = {
    "required": ["listingId", "status"],
    "types": {
        "listingId": str,
        "status": str,
    }
}
```

Test that real responses match contracts:

```python
@pytest.mark.integration
def test_scryfall_response_matches_contract():
    """Verify Scryfall API response matches our contract"""
    api = ScryfallAPI()
    response = api.get_card_by_id("4e2fe951-4820-4555-8cee-621c66ed8620")
    
    assert_contract(response, SCRYFALL_CARD_CONTRACT)
```

---

## Phase 5: Rate Limit & Error Handling

### Rate Limits

| API | Limit | Retry Strategy |
|-----|-------|-----------------|
| **Scryfall** | 10 req/s | Exponential backoff |
| **TCGPlayer** | 1000 req/min | Queue with delays |
| **eBay** | 100 req/sec | Built-in throttling |

### Implementation

```python
# services/rate_limiter.py

class RateLimiter:
    def __init__(self, calls_per_second: float):
        self.min_interval = 1.0 / calls_per_second
        self.last_call_time = 0
    
    def wait_if_needed(self):
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call_time = time.time()

# Use in services
scryfall_limiter = RateLimiter(calls_per_second=10)

class ScryfallAPI:
    @staticmethod
    def get_card_by_id(scryfall_id: str):
        scryfall_limiter.wait_if_needed()
        # ... API call
```

### Retry Logic (Tenacity)

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

class ScryfallAPI:
    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.Timeout)
    )
    def get_card_by_id(scryfall_id: str):
        # ... API call
```

---

## Phase 6: Sandbox Testing Strategy

### eBay Sandbox
- Use `EBAY_SANDBOX_MODE=true` in config
- All listing operations go to sandbox
- No real transactions

### TCGPlayer
- No official sandbox, but test credentials available
- Use test product IDs for testing
- Production after validation

### Google Drive
- Use test folder credentials
- Separate test project in Google Cloud Console
- Permission: Drive API (test scope)

### Scryfall
- Free, no auth required
- Safe to call in tests (respects rate limits)

---

## Phase 7: Continuous Integration

### GitHub Actions Workflow

```yaml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -r requirements.txt pytest vcrpy
      - run: pytest tests/unit/ -v  # Mocks only, always runs
      - run: pytest tests/e2e/ -v

  integration-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -r requirements.txt pytest vcrpy
      - env:
          TCGPLAYER_API_KEY: ${{ secrets.TCGPLAYER_API_KEY }}
          TCGPLAYER_API_SECRET: ${{ secrets.TCGPLAYER_API_SECRET }}
          EBAY_CLIENT_ID: ${{ secrets.EBAY_CLIENT_ID }}
          # ... other secrets
        run: pytest tests/integration/ -v --integration
```

---

## Phase 8: Documentation & Examples

### For Each Service

**ScryfallAPI**
- ✅ Free endpoint, no auth
- ✅ Safe for unit tests
- ✅ Respects rate limits: 10 req/sec
- ✅ Response examples documented

**TCGPlayerAPI**
- ⚠️ Requires credentials
- ⚠️ OAuth token expires after ~30 min
- ✅ Token caching implemented
- ✅ Error cases documented

**eBayAPI**
- ⚠️ Requires OAuth2 refresh token
- ⚠️ Sandbox for testing, Production for live
- ✅ Token refresh logic implemented
- ❌ No direct sandbox reset (manual setup)

**GoogleDriveAPI** (TODO)
- ⚠️ Requires service account credentials
- ⚠️ Requires folder ID whitelisting
- ❌ Not yet implemented
- ✅ Will use official Google API client

---

## Implementation Roadmap

### Sprint 1: Mock Enhancement (This Sprint)
- [ ] Add edge case tests
- [ ] Add rate limit tests
- [ ] Add timeout tests
- [ ] Document contracts
- [ ] Set up VCR.py fixtures

### Sprint 2: Integration Tests
- [ ] Create integration test structure
- [ ] Add Scryfall integration tests
- [ ] Add TCGPlayer integration tests
- [ ] Add eBay integration tests
- [ ] Record cassettes

### Sprint 3: Production Readiness
- [ ] Rate limiter implementation
- [ ] Retry logic (Tenacity)
- [ ] Error reporting
- [ ] Documentation
- [ ] GitHub Actions setup

### Sprint 4: Google Drive Integration
- [ ] GoogleDriveAPI implementation
- [ ] Auto-import watcher service
- [ ] Integration tests
- [ ] Scheduling setup

---

## Success Criteria

- ✅ 100% of mock tests passing
- ✅ All API contracts verified
- ✅ Integration tests pass with real credentials
- ✅ Rate limits respected
- ✅ Error handling covers edge cases
- ✅ 95%+ code coverage
- ✅ Documentation complete
- ✅ CI/CD pipeline configured

---

## Key Principles

1. **Test First**: Write tests before production code
2. **Mocks Always**: Unit tests never call real APIs
3. **Cassettes Next**: Recorded responses in VCS
4. **Integration Last**: Real API calls only when explicit
5. **Contracts Define**: APIs must match expected contracts
6. **Errors Explicit**: All failure modes tested
7. **Rate Limits Respected**: Never hammer external APIs
8. **Credentials Secure**: Never commit API keys

---

## References

- **VCR.py**: https://vcrpy.readthedocs.io/
- **Tenacity**: https://tenacity.readthedocs.io/
- **Pytest**: https://docs.pytest.org/
- **Contract Testing**: https://pact.foundation/

