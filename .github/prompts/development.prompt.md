# MTG Card Inventory & Sales System — Build Prompt

## Project Overview
Build a Magic: The Gathering card inventory management system for a collector with ~440,000 physical cards. The system must be $0/month in ongoing costs, integrate with ManaBox exports, track physical card locations using chaos sorting, and sync listings to eBay and TCGPlayer.

---

## Tech Stack
- **Backend:** Python 3.11+, Flask, SQLite (via SQLAlchemy)
- **Frontend:** Single-page HTML/CSS/JS served by Flask (no frontend framework — keep it simple)
- **Key libraries:** pandas, qrcode, pillow, python-dotenv, requests
- **Database:** SQLite (local, no server required)
- **APIs:** Scryfall (free, no auth), eBay Selling API (OAuth2), TCGPlayer API (API key)

---

## Primary Key Convention
**Always use Scryfall ID (`scryfall_id`) as the unique identifier per card version.** This is the only field guaranteed to be unique across ManaBox exports, Scryfall, eBay, and TCGPlayer. Never use card name alone as a key.

---

## Phase 1 Scope — Build These 4 Modules

### Module 1: ManaBox CSV Import
- Accept a ManaBox CSV export file upload via the web UI
- Parse and validate the following columns (ManaBox standard export format):
  `Name, Set Code, Set Name, Collector Number, Foil, Rarity, Quantity, ManaBox ID, Scryfall ID, Purchase Price, Condition, Language`
- On import, for each card row:
  - Check if `scryfall_id` already exists in the database
  - If new: insert and auto-assign a location code (see Module 3)
  - If existing: update quantity and condition only, never overwrite location
- Show import summary: cards added, cards updated, cards skipped, errors

### Module 2: eBay Listing Sync
- Use the eBay Selling API (Trading API or Inventory API) with OAuth2
- Store eBay OAuth tokens securely in `.env` (never hardcode)
- For each card in inventory marked `list_on_ebay = True`:
  - Check if an active eBay listing already exists (by stored `ebay_listing_id`)
  - If no listing: create a new fixed-price listing using card name, set, condition, foil status, and current TCGPlayer market price as the listing price
  - If listing exists: sync quantity and price only
- Implement a `/sync/ebay` endpoint that runs the sync job
- Log all API calls and responses to `logs/ebay_sync.log`
- Handle eBay API rate limits gracefully (exponential backoff)

### Module 3: TCGPlayer Sync
- Use the TCGPlayer API (requires API key stored in `.env`)
- Fetch current market price for each card using `scryfall_id` → TCGPlayer product ID mapping
- Store fetched prices in a `prices` table with a `fetched_at` timestamp
- Never fetch prices more than once per 24 hours per card (check timestamp before calling API)
- Expose a `/sync/prices` endpoint that updates stale prices in batches of 100
- Display current market price and price fetched date in the card detail view

### Module 4: QR Code Location Tracking (Chaos Sorting)
**Chaos sorting means cards are stored in the order they were scanned — no alphabetical or set-based sorting. The database IS the organisation system.**

Location code format: `BOX-{box_number:04d}-SLOT-{slot_number:04d}`
Example: `BOX-0012-SLOT-0047`

- On first import of any card, auto-assign the next available slot in the current open box
- Default box capacity: 500 cards (configurable in `config.py`)
- When a box reaches capacity, automatically open the next box number
- Generate a printable QR code for each box that links to `/box/{box_number}` — a mobile-friendly page listing all cards in that box
- Provide a `/card/{scryfall_id}/location` endpoint returning the box and slot for a given card
- Provide a `/box/{box_number}` page showing all cards in that box with name, set, condition, foil, and market price
- Include a "Mark as Sold" button per card that clears the eBay listing ID and marks the slot as vacant

---

## Database Schema
Create the following tables in SQLite:

```sql
cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scryfall_id TEXT UNIQUE NOT NULL,
  manabox_id TEXT,
  name TEXT NOT NULL,
  set_code TEXT,
  set_name TEXT,
  collector_number TEXT,
  foil BOOLEAN DEFAULT FALSE,
  rarity TEXT,
  quantity INTEGER DEFAULT 1,
  condition TEXT,
  language TEXT DEFAULT 'en',
  purchase_price REAL,
  location_code TEXT,
  box_number INTEGER,
  slot_number INTEGER,
  list_on_ebay BOOLEAN DEFAULT FALSE,
  ebay_listing_id TEXT,
  tcgplayer_product_id TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

prices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scryfall_id TEXT NOT NULL,
  market_price REAL,
  low_price REAL,
  high_price REAL,
  fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (scryfall_id) REFERENCES cards(scryfall_id)
)

boxes (
  box_number INTEGER PRIMARY KEY,
  capacity INTEGER DEFAULT 500,
  current_count INTEGER DEFAULT 0,
  qr_code_path TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

sync_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sync_type TEXT,
  status TEXT,
  cards_processed INTEGER,
  errors INTEGER,
  run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

---

## Project File Structure
```
mtg-inventory/
├── app.py                  # Flask app entry point
├── config.py               # BOX_CAPACITY, API keys from .env, DB path
├── models.py               # SQLAlchemy models matching schema above
├── database.py             # DB init, session management
├── routes/
│   ├── inventory.py        # CSV import, card CRUD, search
│   ├── ebay.py             # eBay sync endpoints
│   ├── tcgplayer.py        # Price sync endpoints
│   └── locations.py        # QR codes, box views, location lookup
├── services/
│   ├── manabox.py          # CSV parsing and import logic
│   ├── ebay_api.py         # eBay API client (OAuth2, rate limiting)
│   ├── tcgplayer_api.py    # TCGPlayer API client
│   ├── scryfall_api.py     # Scryfall API client (card enrichment)
│   └── location_engine.py  # Chaos sort assignment logic
├── templates/
│   ├── base.html           # Base layout
│   ├── dashboard.html      # Overview: total cards, value, sync status
│   ├── import.html         # CSV upload page
│   ├── card_detail.html    # Single card view with location + price
│   └── box_view.html       # Mobile-friendly box contents page
├── static/
│   ├── style.css
│   └── app.js
├── qrcodes/                # Generated QR code PNGs (gitignored)
├── logs/                   # Sync logs (gitignored)
├── .env.example            # Template for required env vars
├── requirements.txt
└── README.md
```

---

## Environment Variables (.env.example)
```
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
EBAY_REFRESH_TOKEN=
EBAY_SANDBOX_MODE=True
TCGPLAYER_API_KEY=
TCGPLAYER_API_SECRET=
BOX_CAPACITY=500
DATABASE_URL=sqlite:///mtg_inventory.db
FLASK_SECRET_KEY=
BASE_URL=http://localhost:5000
```

---

## Key Behaviours & Constraints
- **Never delete a card's location once assigned** — even if sold, mark as vacant but preserve the slot history
- **Scryfall API is free** — use it to enrich card data (image URIs, prices, legality) but cache responses and respect the 10 requests/second rate limit
- **eBay sandbox first** — default `EBAY_SANDBOX_MODE=True` so no real listings are created during development
- **Batch all API calls** — never call external APIs in a loop without batching and rate limiting
- **Mobile-first box view** — the `/box/{box_number}` page will be used on a phone while physically pulling cards, so it must be fast and readable on small screens
- **No authentication required** — this is a local tool running on localhost, skip user login entirely

---

## Start Here
1. Scaffold the project structure and `requirements.txt`
2. Set up Flask app, SQLAlchemy, and database init with the schema above
3. Build Module 1 (ManaBox CSV import) end-to-end first — this populates the database for all other modules to use
4. Build Module 4 (location tracking) second — it runs automatically during import
5. Build Module 3 (TCGPlayer prices) third — needed before eBay listings can be priced
6. Build Module 2 (eBay sync) last

Do not move to the next module until the current one has a working UI and passing unit tests.