# Demo Implementation Guide

## Overview
The MTG inventory demo showcases three main workflows. This guide maps demo features to backend implementation requirements.

---

## 1. BASE STYLING ✅ COMPLETED
Enhanced base.html and style.css with modern dark theme design:

**Changes Made:**
- Added Google Fonts import (Space Mono, Syne)
- Implemented CSS variables for theming
- Redesigned navigation with logo and sidebar-style layout
- Updated message/alert styling with icons and animations
- Added button, form, table, and badge component styles
- Responsive design for mobile/tablet

**Files Modified:**
- `templates/base.html` - Enhanced HTML structure
- `static/style.css` - Complete style overhaul

---

## 2. CSV IMPORT WORKFLOW

### Current Implementation ✅
- [x] CSV upload endpoint (`POST /inventory/import`)
- [x] CSV parsing with pandas
- [x] Data validation
- [x] Location assignment (chaos sort)
- [x] Database persistence

### Demo Features Needing Implementation

#### 2.1 File Upload with Progress Bar/Streaming
**Status**: Partial (upload works, progress UI missing)
**What's needed:**
```
- Add progress bar UI to import.html
- Implement server-sent events (SSE) for live progress updates
- Show real-time stats: Added, Updated, Skipped, Errors
- Animated counter increments (like in demo)
```

**Implementation:**
```python
# In routes/inventory.py
@app.route('/inventory/import-progress')
def import_progress_stream():
    """SSE endpoint for progress updates"""
    # Yield progress events as CSV processes
    yield f"data: {json.dumps({'loaded': count})}\n\n"
```

```javascript
// In static/app.js
const eventSource = new EventSource('/inventory/import-progress');
eventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    updateProgressBar(data.loaded);
};
```

#### 2.2 Preview Table with Results
**Status**: Partial (works in tests, not displayed in UI)
**What's needed:**
```
- Display imported cards in table format
- Show location codes (BOX-0001-SLOT-0001)
- Show card metadata (set, condition, foil status)
- Show status badges (new, updated, skipped)
```

**Implementation:**
- Modify `import.html` template to render preview table
- Use card data returned from import endpoint
- Style table with CSS variables (already in style.css)

#### 2.3 Real-Time Card Data
**Status**: Not implemented
**What's needed:**
```
- Scryfall API integration for card images
- Card name and set retrieval
- Price data from TCGPlayer
- Display in preview before import
```

---

## 3. CHAOS SORT WORKFLOW

### Current Implementation ✅
- [x] Location engine (box/slot assignment)
- [x] Location code generation
- [x] Box capacity management
- [x] Database models for locations

### Demo Features Needing Implementation

#### 3.1 Box Grid View
**Status**: Not implemented in actual app
**What's needed:**
```
- Endpoint: GET /locations/boxes
  Returns: List of all boxes with:
  - Box number
  - Current card count
  - Capacity
  - Fill percentage
  - Cards in box

- Template: box_view.html
  Display grid of boxes (done in demo)
  Interactive box selection
  Show/hide card details
```

**Implementation:**
```python
# In routes/locations.py
@app.route('/locations/boxes')
def get_boxes():
    """Return all boxes with stats"""
    boxes = db.session.query(Box).all()
    return jsonify([{
        'number': b.box_number,
        'count': len(b.cards),
        'capacity': 500,
        'fill_percent': (len(b.cards) / 500) * 100
    } for b in boxes])
```

#### 3.2 Box Detail View
**Status**: Not implemented
**What's needed:**
```
- Show all cards in selected box
- Display slot codes
- Show card name, set, condition, price
- Allow filtering/searching
- Generate QR codes for box (print feature)
```

**Implementation:**
- Extend `GET /locations/boxes/<box_id>`
- Include full card details in response
- QR code generation (see below)

#### 3.3 QR Code Generation
**Status**: Partially implemented
**What's needed:**
```
- Generate QR codes for each box
- Store as image files (qrcodes/ folder exists)
- Display in box view
- PDF printing capability
```

**Implementation:**
```python
# In services/
import qrcode

def generate_box_qr(box_number):
    """Generate QR code for box"""
    code = qrcode.QRCode()
    code.add_data(f"BOX-{box_number:04d}")
    code.make()
    img = code.make_image()
    img.save(f'qrcodes/BOX-{box_number:04d}.png')
```

---

## 4. EBAY LISTING WORKFLOW

### Current Implementation ✅
- [x] eBay API client (OAuth, listing creation)
- [x] TCGPlayer pricing integration
- [x] Listing data models

### Demo Features Needing Implementation

#### 4.1 Card Selection Form
**Status**: Not implemented in actual app
**What's needed:**
```
- Form to select card from inventory
- Dropdowns for:
  - Card name (auto-complete)
  - Set (auto-populated)
  - Condition (NM, LP, MP, HP, PO)
  - Foil status (yes/no)
  - Quantity
  - Price override

- Real-time price suggestion from TCGPlayer
```

**Implementation:**
```html
<!-- In templates/ebay_listing.html -->
<form>
    <input type="text" id="cardName" list="cardList" placeholder="Card name...">
    <datalist id="cardList">
        <!-- Populated by AJAX -->
    </datalist>
    <select id="cardCondition">
        <option>NM</option>
        <option>LP</option>
        <option>MP</option>
    </select>
    <input type="number" id="cardPrice" placeholder="Price">
</form>
```

#### 4.2 eBay Listing Preview
**Status**: Not implemented
**What's needed:**
```
- Real-time preview styled like eBay listing
- Show:
  - Card title with set and condition
  - Price formatted as US $XX.XX
  - Condition description
  - Create/Watch buttons (non-functional in demo)
- Update as form changes
```

**Implementation:**
```javascript
// In static/app.js
function updatePreview() {
    const name = document.getElementById('cardName').value;
    const price = parseFloat(document.getElementById('cardPrice').value);
    document.getElementById('previewTitle').textContent = `${name} ...`;
    document.getElementById('previewPrice').textContent = 
        `US $${price.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
}
```

#### 4.3 Batch Listing Queue
**Status**: API exists, UI missing
**What's needed:**
```
- Add multiple cards to queue before syncing
- Display queue with:
  - Card name
  - Price
  - Status (pending, syncing, done, error)
  - eBay listing ID when created
- Bulk sync button
- Real-time status updates
```

**Implementation:**
```python
# In routes/ebay.py
@app.route('/ebay/listings', methods=['POST'])
def create_bulk_listings():
    """Create multiple listings at once"""
    listing_data = request.json['listings']
    results = []
    for listing in listing_data:
        result = ebay_api.create_listing(listing)
        results.append(result)
    return jsonify(results)
```

#### 4.4 Sandbox/Production Mode Toggle
**Status**: Placeholder in demo
**What's needed:**
```
- Configuration for sandbox vs production
- eBay sandbox API endpoint setup
- Warning badge when in sandbox mode
- Ability to test without real listings
```

**Implementation:**
```python
# In config.py
EBAY_SANDBOX = True  # Toggle for development
EBAY_API_URL = (
    'https://api.sandbox.ebay.com' if EBAY_SANDBOX
    else 'https://api.ebay.com'
)
```

---

## 5. DATA FLOW REQUIREMENTS

### 5.1 Database Schema
**Current Status**: ✅ Mostly complete

**What exists:**
- Card model with scryfall_id, name, set
- Box model for location organization
- Location model for slot tracking
- Pricing model (might need extension)

**What may need adding:**
```python
# For eBay listings
class EBayListing(db.Model):
    id = db.Column(db.String(20), primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey('card.id'))
    title = db.Column(db.String(100))
    price = db.Column(db.Float)
    status = db.Column(db.String(20))  # active, sold, draft
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)

# For QR codes
class BoxQRCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    box_id = db.Column(db.Integer, db.ForeignKey('box.id'))
    qr_file = db.Column(db.String(255))
    generated_at = db.Column(db.DateTime)
```

### 5.2 API Response Formats
All endpoints should return consistent JSON format matching demo expectations.

**Example:**
```json
{
    "success": true,
    "data": { ... },
    "stats": {
        "added": 110247,
        "updated": 8432,
        "skipped": 312,
        "errors": 7
    },
    "timestamp": "2026-03-04T15:30:00Z"
}
```

---

## 6. FRONTEND TEMPLATES TO UPDATE

### 6.1 import.html
**Current**: Basic form
**Needed:**
- [ ] Drag-and-drop zone styling
- [ ] Progress bar with animation
- [ ] Live stats counter
- [ ] Preview table after import

### 6.2 dashboard.html
**Current**: Likely basic
**Needed:**
- [ ] Overview cards (total cards, boxes, value)
- [ ] Recent imports list
- [ ] Quick actions
- [ ] Charts/analytics (stretch goal)

### 6.3 box_view.html
**Current**: Exists but may be incomplete
**Needed:**
- [ ] Grid of boxes
- [ ] Click to view details
- [ ] QR code display
- [ ] Slot contents

### 6.4 New: ebay_listing.html
**Status**: Needs creation
**Content:**
- Card selection form
- Real-time price lookup
- eBay preview
- Batch queue
- Sync controls

### 6.5 New: card_search.html
**Status**: Needs creation
**Content:**
- Search all inventory
- Filter by condition, foil, box
- View card details
- Quick actions (list, move, edit)

---

## 7. JAVASCRIPT ENHANCEMENTS

### 7.1 app.js Additions Needed
```javascript
// Form handling
function updatePreview() { ... }
function addToQueue() { ... }
function renderQueue() { ... }

// Real-time updates
class EventStreamHelper {
    constructor(endpoint) { ... }
    onProgress(callback) { ... }
}

// CSV upload
function handleFileDrop(e) { ... }
function simulateProgressBar() { ... }

// eBay sync
function runSync() { ... }
function publishListing(id) { ... }

// Pagination/search
function filterCards(query) { ... }
function loadMore() { ... }
```

---

## 8. IMPLEMENTATION PRIORITY

### Phase 1: UI/UX Polish ⚡ START HERE
- [x] Styling enhancements (JUST DONE)
- [ ] Update import.html with progress/preview
- [ ] Create ebay_listing.html template
- [ ] Add responsive design refinements

### Phase 2: Core Features
- [ ] Progress streaming (SSE)
- [ ] Box grid view with QR codes
- [ ] eBay listing form with real prices
- [ ] Batch queue system

### Phase 3: Advanced Features
- [ ] Real-time card search
- [ ] Analytics dashboard
- [ ] Inventory reports
- [ ] API documentation

---

## 9. TESTING INTEGRATION

All new features should follow existing test patterns:

```
✅ Already tested (in claude.md):
- CSV import (test_import.py)
- Services/APIs (test_services.py)
- E2E workflows (test_e2e.py)
- Chaos sort (test_chaos_sort.py)

❌ Not yet tested:
- Progress streaming
- Box view endpoints
- eBay listing creation UI
- QR code generation
- Real-time updates
```

---

## 10. QUICK REFERENCE: What's Done vs TODO

| Feature | Backend | Frontend | Tests |
|---------|---------|----------|-------|
| CSV Import | ✅ | ⚠️ (basic) | ✅ |
| Chaos Sort | ✅ | ❌ | ✅ |
| eBay Listings | ✅ | ❌ | ⚠️ (mock) |
| QR Codes | ❌ | ❌ | ❌ |
| Progress Bar | ❌ | ❌ | ❌ |
| Pricing | ✅ | ❌ | ✅ |
| Box Grid | ❌ | ❌ | ❌ |
| Card Search | ❌ | ❌ | ❌ |

---

## 11. CONFIGURATION CHECKLIST

Ensure these are properly configured for demo:

```yaml
Environment Variables:
  - SCRYFALL_API_URL: https://api.scryfall.com
  - TCGPLAYER_API_KEY: <your-key>
  - TCGPLAYER_API_SECRET: <your-secret>
  - EBAY_CLIENT_ID: <your-id>
  - EBAY_CLIENT_SECRET: <your-secret>
  - EBAY_SANDBOX: true (for demo)
  - BOX_CAPACITY: 500
  - DATABASE_URL: sqlite:///inventory.db

Directories:
  - qrcodes/ exists and is writable
  - logs/ exists and is writable
  - uploads/ exists and is writable

Services:
  - Scryfall API (public, no key needed)
  - TCGPlayer API (requires credentials)
  - eBay Sandbox API (requires test account)
```

---

## Next Steps
1. **Immediate**: Review import.html and add progress bar UI
2. **Short-term**: Create ebay_listing.html template
3. **Medium-term**: Implement box grid and QR codes
4. **Long-term**: Add advanced features (search, analytics)

For detailed implementation of any section, see the code comments in the test files (test_import.py, test_e2e.py, test_services.py).
