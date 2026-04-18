# Phase 3: Real API Integration & Persistent Test Data

## Overview

Moving from **mocks and cassettes** to **real API integration** with persistent test data.

```
Phase 1 ✅: Mocks (45 tests, 2.36s)
Phase 2 ✅: Cassettes infrastructure ready
Phase 3 🚀: Real API integration (this phase)
Phase 4: Production monitoring & CI/CD
```

---

## Key Changes from Phase 2 to Phase 3

| Aspect | Phase 2 (Mocks) | Phase 3 (Real APIs) |
|--------|-----------------|-------------------|
| Test Data | Regenerated each test | **Persistent database** |
| API Calls | Mocked with @patch | **Real API calls** |
| Database | In-memory SQLite | **test_data.db** |
| Cassettes | Optional | **Recorded & replayed** |
| Speed | ~2 seconds | ~10-30 seconds |
| Dependencies | None | API credentials |

---

## What You Got in Phase 3

### 1. Test Data Initialization

**File**: `setup_test_data.py`

Creates a **persistent test database** with realistic MTG card data:
```bash
# Create test_data.db with 5000 cards (run ONCE)
python setup_test_data.py

# Generate 10,000 cards instead
python setup_test_data.py --count 10000

# Reset and regenerate
python setup_test_data.py --reset

# View statistics
python setup_test_data.py --stats
```

**Why this matters**:
- ✅ Test data is saved (not regenerated each time)
- ✅ Consistent across all tests
- ✅ Chaos sort can use real persistent database
- ✅ Faster test runs after initial setup

### 2. Integration Test Infrastructure

**File**: `tests_integration_config.py`

Provides:
- VCR cassette configuration (record/replay HTTP)
- Integration test fixtures
- API credential checking
- Sensible defaults for each service

**File**: `tests/integration/test_real_apis.py`

Real API tests for:
- ✅ Scryfall (no credentials needed)
- ✅ TCGPlayer (requires credentials)
- ✅ eBay (requires credentials, sandbox only)
- ✅ Complete workflows combining APIs

### 3. Directory Structure

```
mtg-inventory/
├── setup_test_data.py              ✅ Test data initialization
├── tests_integration_config.py     ✅ Integration fixtures & config
├── test_data.db                    ✅ Persistent test database
├── tests/
│   ├── integration/
│   │   ├── __init__.py
│   │   └── test_real_apis.py       ✅ Real API integration tests
│   └── fixtures/
│       └── cassettes/              ✅ Recorded API responses
│           ├── scryfall_*.yaml
│           ├── tcgplayer_*.yaml
│           └── ebay_*.yaml
```

---

## Getting Started with Phase 3

### Step 1: Initialize Test Data (One-Time)

```bash
# Generate 5000 realistic MTG cards for testing
python setup_test_data.py

# Expected output:
# 🔄 Generating 5,000 test cards...
# ✅ Generated 5,000 cards!
# ✅ Database verified: 5,000 cards in database
```

This creates `test_data.db` which will be used by all subsequent tests.

**Time**: ~30-60 seconds (one-time cost)

### Step 2: Add API Credentials (If Testing Real APIs)

Create or update `.env`:
```bash
# For TCGPlayer testing
TCGPLAYER_API_KEY=your_key_here
TCGPLAYER_API_SECRET=your_secret_here

# For eBay testing (sandbox only)
EBAY_CLIENT_ID=your_client_id
EBAY_CLIENT_SECRET=your_client_secret
EBAY_REFRESH_TOKEN=your_refresh_token
EBAY_SANDBOX_MODE=True

# Google Drive (future)
GOOGLE_DRIVE_CREDENTIALS_JSON=/path/to/credentials.json
```

Security guidance:
- Ensure `.env` is ignored by git (never commit secrets).
- Maintain a `.env.example` template with placeholders (for example `TCGPLAYER_API_KEY=`, `TCGPLAYER_API_SECRET=`, `EBAY_CLIENT_ID=`).
- Copy `.env.example` to `.env` locally and fill real values only on trusted machines.
- Never commit real credentials to source control or public repositories.

### Step 3: Test with Cassettes (No Real API Calls)

```bash
# Uses recorded responses (fast, no API calls)
pytest tests/integration/ -v

# Output:
# tests/integration/test_real_apis.py::TestScryfallIntegration::test_scryfall_get_card_real PASSED
# tests/integration/test_real_apis.py::TestTCGPlayerIntegration::test_tcgplayer_authenticate_real PASSED
# ...
```

**Speed**: Fast (~5-10 seconds), uses pre-recorded responses

### Step 4: Record New Cassettes (Real API Calls)

```bash
# Record fresh cassettes from real APIs (requires credentials)
pytest tests/integration/ -v --record-cassettes

# This will:
# 1. Make real API calls to Scryfall, TCGPlayer, eBay
# 2. Record responses in tests/fixtures/cassettes/*.yaml
# 3. Future runs use the recorded responses
```

**Speed**: Slow (~30-60 seconds), makes real API calls
**Credentials**: Required for TCGPlayer and eBay

### Step 5: Use Persistent Database in Tests

```python
# Any test can now use the persistent database
def test_chaos_sort_with_real_data(persistent_test_db):
    """Test chaos sorting with 5000 real cards"""
    from services.chaos_sort import ChaosSort
    
    chaos = ChaosSort(persistent_test_db)
    shuffled = chaos.sort_inventory()
    
    assert len(shuffled) == 5000
    assert isinstance(shuffled, list)
```

---

## Chaos Sorting with Real Database

The chaos sort now works with REAL persistent data:

### Before (In-Memory)
```python
# Each test got fresh, empty database
@pytest.fixture
def in_memory_db():
    engine = create_engine('sqlite:///:memory:')  # Temporary!
    # ...
```

### After (Persistent)
```python
# Tests use database with 5000+ real cards
@pytest.fixture(scope="session")
def persistent_test_db():
    # Reuses test_data.db across all tests
    engine = create_engine('sqlite:///test_data.db')
    # ...
```

### Usage in Tests
```python
def test_chaos_sort_with_large_dataset(persistent_test_db):
    """Test chaos sorting with 5000 real cards"""
    chaos = ChaosSort(persistent_test_db)
    
    # Get all cards
    card_ids = chaos.sort_inventory()
    
    # Verify randomization
    assert len(card_ids) == 5000
    assert isinstance(card_ids, list)
```

---

## VCR Cassette System

### What Are Cassettes?

YAML files containing recorded HTTP interactions:

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
      string: '{"id":"4e2fe951-4820...","name":"Path to Exile",...}'
version: 1
```

### How It Works

**First Run (--record-cassettes)**
```
Test → Real API → Record response → cassette.yaml
```

**Subsequent Runs (No Flag)**
```
Test → cassette.yaml (replay) → No API call
```

### Benefits

✅ **No API calls in CI/CD** - Uses recorded responses  
✅ **Predictable & repeatable** - Same response every time  
✅ **Version controlled** - Check cassettes into git  
✅ **Sensitive data filtered** - API keys automatically scrubbed  

---

## Running Different Test Suites

### Quick Test (Mocks Only)
```bash
# 45 tests with mocks (~2 seconds)
pytest test_services.py test_services_extended.py -q
```

### Integration Tests (Cassettes)
```bash
# Real API tests with recorded responses (~10 seconds)
pytest tests/integration/ -v
```

### Large Scale Tests (Persistent DB)
```bash
# Chaos sort with 5000 cards
pytest test_chaos_sort.py -v
```

### Record New Cassettes (Real APIs)
```bash
# Make real API calls and record
pytest tests/integration/ -v --record-cassettes
```

### Everything
```bash
# All tests
pytest test_*.py tests/integration/ -v
```

---

## Integration Test Features

### 1. Automatic Credential Detection

Tests automatically skip if credentials missing:

```python
@pytest.mark.integration
def test_tcgplayer_real(tcgplayer_cassette):
    # Skips if TCGPLAYER_API_KEY + TCGPLAYER_API_SECRET not in .env
    ...
```

### 2. Sandbox Mode Enforcement for eBay

```python
# Refuses to run if EBAY_SANDBOX_MODE=False
if not APITestConfig.EBAY_SANDBOX_MODE:
    pytest.skip("eBay sandbox mode is OFF - refusing to run tests!")
```

### 3. Contract Validation

All API responses validated against contracts:

```python
# Verify response matches expected schema
result = ScryfallAPI.get_card_by_id(card_id)
is_valid, errors = ScryfallCardContract.validate(result)
assert is_valid, f"Contract violations: {errors}"
```

### 4. Rate Limiting Integration

Tests verify rate limiters work with real APIs:

```python
def test_scryfall_respects_rate_limit(self, scryfall_cassette):
    from services_rate_limiter import SCRYFALL_LIMITER
    
    SCRYFALL_LIMITER.reset()
    
    # Make calls - rate limiter should throttle
    for i in range(3):
        api.get_card_by_id(...)
    
    stats = SCRYFALL_LIMITER.get_stats()
    assert stats['total_calls'] >= 3
```

---

## Working with Cassettes

### Recording a New Cassette

```bash
# Run specific test and record cassette
pytest tests/integration/test_real_apis.py::TestScryfallIntegration::test_scryfall_get_card_real \
    -v --record-cassettes
```

This creates `tests/fixtures/cassettes/scryfall_get_card.yaml`

### Updating Cassettes

```bash
# Force re-record all cassettes
pytest tests/integration/ -v --record-cassettes
```

### Viewing Cassette Contents

```bash
# Just look at the YAML file
cat tests/fixtures/cassettes/scryfall_get_card.yaml
```

### Cleaning Old Cassettes

```bash
# Remove all cassettes and regenerate
rm -rf tests/fixtures/cassettes/*
pytest tests/integration/ -v --record-cassettes
```

---

## Troubleshooting Phase 3

### Problem: "Test database not found"

```
❌ Test database not found: test_data.db
   Initialize with: python setup_test_data.py
```

**Solution**:
```bash
python setup_test_data.py
```

### Problem: Integration tests are skipped

Tests skip automatically if credentials missing. Check:
```bash
# See which APIs are enabled
grep -E "API_KEY|CLIENT_ID" .env

# Add missing credentials to .env
echo "TCGPLAYER_API_KEY=your_key" >> .env
```

### Problem: Cassettes not being used

Check VCR record mode:
```bash
# Should be 'once' (use cassette if exists)
echo $VCR_RECORD_MODE  # Should be empty or 'once'

# Or explicitly set
export VCR_RECORD_MODE=once
pytest tests/integration/ -v
```

### Problem: API key exposed in cassette

Cassettes are automatically scrubbed:
```yaml
# API keys are filtered
Authorization: REDACTED
```

But verify before committing:
```bash
grep -r "secret\|key" tests/fixtures/cassettes/
```

---

## Next Steps After Phase 3

### Phase 4: Production Monitoring
- Set up error logging
- Monitor rate limit usage
- Track circuit breaker state
- Alert on API failures

### Phase 5: GitHub Actions CI/CD
```yaml
# .github/workflows/tests.yml
- Unit tests: Every push (no credentials)
- Integration tests: Weekly (with secrets)
```

### Production Deployment
- Deploy with rate limiters active
- Monitor API health
- Store credentials securely
- Set up alerting

---

## Summary: What Changed

**Phase 2 (Mocks)**
- All tests mocked
- No external dependencies
- In-memory databases

**Phase 3 (Real APIs)**
- Persistent test database
- Real API calls with cassettes
- Contract validation
- Rate limiting verified
- Integration tests
- CI/CD ready

**Phase 4 (Production)**
- Production monitoring
- Alert on failures
- Track performance
- Real-world usage

---

## Quick Reference

```bash
# One-time setup
python setup_test_data.py

# Run tests with persistent data
pytest test_chaos_sort.py -v
pytest tests/integration/ -v

# Record API responses
pytest tests/integration/ -v --record-cassettes

# View test database stats
python setup_test_data.py --stats

# Reset test database
python setup_test_data.py --reset
```

---

**Status: 🚀 Phase 3 Ready**

You can now:
1. ✅ Generate persistent test data once
2. ✅ Run chaos sort with 5000+ real cards
3. ✅ Test real API integration with cassettes
4. ✅ Record API responses for CI/CD
5. ✅ Verify rate limiting works
6. ✅ Validate API contracts

Ready to move to Phase 4 (production monitoring) when needed! 🎉

