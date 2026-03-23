# API Quick Reference

## 📋 Documentation Files

This API contract is documented across three formats:

| File | Format | Purpose | Import To |
|------|--------|---------|-----------|
| [`API_CONTRACT.md`](API_CONTRACT.md) | Markdown | Complete spec with examples | Browser/IDE |
| [`openapi.yaml`](openapi.yaml) | OpenAPI 3.0 | Standardized API spec | [Swagger UI](https://editor.swagger.io), [ReDoc](https://redoc.ly) |
| [`postman_collection.json`](postman_collection.json) | Postman v2.1 | Ready-to-test requests | [Postman](https://www.postman.com) |

---

## 🚀 Quick Start

### Option 1: Use Postman (Easiest)

1. Download [Postman](https://www.postman.com/downloads/)
2. Click **Import** → Choose file → Select `postman_collection.json`
3. Set `{{base_url}}` to `http://localhost:5000`
4. Start testing!

### Option 2: Use Swagger UI

1. Visit [Swagger Editor](https://editor.swagger.io)
2. Paste contents of `openapi.yaml`
3. Try out requests directly in browser

### Option 3: Command Line (cURL)

```bash
# Health check
curl http://localhost:5000/api/health

# Search cards
curl "http://localhost:5000/api/cards/search?q=Ragavan"

# List boxes
curl http://localhost:5000/api/boxes
```

---

## 📌 Common Endpoints

### Health & Status
```
GET  /api/health                   # Check API status
```

### Cards
```
GET  /api/cards/search?q=<query>   # Search cards
GET  /api/cards                    # List all cards
GET  /api/cards/:id                # Get card details
PUT  /api/cards/:id                # Update card
DELETE /api/cards/:id              # Delete card
```

### Locations (Boxes)
```
GET  /api/boxes                    # List all boxes
GET  /api/boxes/:id                # Get box details
POST /api/boxes/:id/qr             # Generate QR code
```

### Inventory Management
```
POST /inventory/import             # Upload CSV
```

### Pricing
```
GET  /api/pricing/:scryfall_id     # Get card pricing
POST /api/pricing/refresh          # Refresh all prices
```

### eBay Integration
```
GET  /api/ebay/listings            # List listings
POST /api/ebay/listings            # Create listing
PUT  /api/ebay/listings/:id        # Update listing
DELETE /api/ebay/listings/:id      # Delete listing
```

---

## 🔐 Authentication

### Current Status: ⚠️ Not Yet Implemented

Protected endpoints marked with 🔒 will require Bearer token authentication:

```http
Authorization: Bearer <token>
```

**To test protected endpoints now:**
- They will be accessible without authentication during development
- Add `auth_token` variable in Postman when ready

---

## 📝 Request Examples

### Search Cards
```bash
curl "http://localhost:5000/api/cards/search?q=Ragavan&limit=10"
```

### Import CSV
```bash
curl -X POST \
  -F "file=@export.csv" \
  http://localhost:5000/inventory/import
```

### Create eBay Listing (with auth)
```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "card_id": 1,
    "price": 52.99,
    "quantity": 1,
    "condition_id": 3000,
    "category_id": "19476"
  }' \
  http://localhost:5000/api/ebay/listings
```

---

## ✅ Response Format

### Success Response (200 OK)
```json
{
  "success": true,
  "data": { ... },
  "pagination": {
    "total": 100,
    "limit": 10,
    "offset": 0,
    "has_more": true
  }
}
```

### Error Response (4xx/5xx)
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested card does not exist",
    "status": 404,
    "timestamp": "2026-03-04T15:30:00Z",
    "request_id": "req_abc123xyz"
  }
}
```

---

## 🔧 Status Codes

| Code | Meaning |
|------|---------|
| `200` | OK - Success |
| `201` | Created - Resource created |
| `202` | Accepted - Operation queued |
| `204` | No Content - Successful DELETE |
| `400` | Bad Request - Invalid parameters |
| `401` | Unauthorized - Missing/invalid auth |
| `403` | Forbidden - Insufficient permissions |
| `404` | Not Found - Resource doesn't exist |
| `409` | Conflict - Duplicate resource |
| `429` | Too Many Requests - Rate limited |
| `500` | Internal Server Error |
| `503` | Service Unavailable |

---

## 📚 Query Parameter Types

| Type | Example | Notes |
|------|---------|-------|
| string | `?q=Ragavan` | URL encoded |
| integer | `?limit=10` | Must be valid number |
| boolean | `?foil=true` | `true` or `false` |
| float | `?min_price=10.50` | Decimal allowed |
| enum | `?sort=name` | Predefined values only |

---

## 💾 Card Conditions

All cards use standard MTG condition abbreviations:

| Code | Meaning |
|------|---------|
| `NM` | Near Mint - Perfect/near perfect |
| `LP` | Light Play - Barely visible wear |
| `MP` | Moderate Play - Observable wear |
| `HP` | Heavy Play - Significant wear |
| `PO` | Poor - Heavy play/damage visible |

---

## 📊 Data Fields

### Card Object Key Fields
```json
{
  "id": 1,                           // Database ID
  "scryfall_id": "uuid-xxx",         // Scryfall UUID
  "name": "Ragavan, Nimble Pilferer",
  "set_code": "MH2",                 // Set abbreviation
  "collector_number": "138",
  "foil": false,                     // Foil variant
  "condition": "NM",                 // Card condition
  "quantity": 1,                     // In inventory
  "location_code": "BOX-0001-SLOT-0001", // Storage location
  "market_price": 48.50              // Current TCGPlayer price
}
```

### Box Object Key Fields
```json
{
  "id": 1,                           // Box ID
  "number": 1,                       // Box number
  "capacity": 500,                   // Max cards
  "current_count": 500,              // Cards in box
  "fill_percentage": 100.0           // (current/capacity)*100
}
```

---

## 🔄 Pagination

All list endpoints support pagination:

```bash
?limit=20&offset=0&sort=name&order=asc
```

**Parameters**:
- `limit` - Records per page (default 50, max 100)
- `offset` - Skip N records (default 0)
- `sort` - Sort field (varies by endpoint)
- `order` - `asc` or `desc` (default desc)

**Response includes**:
```json
{
  "pagination": {
    "total": 2847,
    "limit": 20,
    "offset": 0,
    "has_more": true,
    "pages": 143
  }
}
```

---

## 🛠️ Development Helpers

### Testing with curl

**Set base URL as variable**:
```bash
BASE_URL="http://localhost:5000"

# Then use in requests:
curl "$BASE_URL/api/health"
curl "$BASE_URL/api/cards/search?q=Ragavan"
```

### Pretty print JSON
```bash
# Pipe through jq
curl "$BASE_URL/api/health" | jq .

# Or use Python
curl "$BASE_URL/api/health" | python -m json.tool
```

### Check endpoint availability
```bash
curl -I http://localhost:5000/api/health
```

---

## 📱 Mobile & Client Integration

### Headers to Include
```http
Content-Type: application/json
Accept: application/json
User-Agent: MTGInventory-Client/1.0
X-Requested-With: XMLHttpRequest
```

### CORS (Cross-Origin)

⚠️ **Currently not configured** - Same-origin requests only

Will need to configure for web/mobile clients:
```python
# Future: app.py
from flask_cors import CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})
```

---

## 🐛 Debugging Tips

### Enable Request Logging
```bash
# In Flask terminal, will show all requests
```

### Check Database
```bash
# View SQLite database
sqlite3 mtg_inventory.db

# List tables
.tables

# Query cards
SELECT COUNT(*) FROM cards;
```

### Verify JSON Syntax
```bash
# Validate request body
python -m json.tool < request.json
```

---

## 📖 Learn More

- **Full Specification**: See [`API_CONTRACT.md`](API_CONTRACT.md) for complete documentation
- **OpenAPI/Swagger**: See [`openapi.yaml`](openapi.yaml) for machine-readable spec
- **Interactive Testing**: Import [`postman_collection.json`](postman_collection.json) into Postman

---

## ❓ FAQ

**Q: How do I authenticate?**  
A: Authentication is planned. Currently all endpoints are public for testing.

**Q: What's the rate limit?**  
A: No limit during development. Production will enforce limits.

**Q: Can I get help with the API?**  
A: Check this quick reference, full API_CONTRACT.md, or test with Postman.

**Q: Are the endpoints versioned?**  
A: Currently v0.1.0. Version in URL will be added when APIs stabilize.

**Q: What timezone are timestamps in?**  
A: All timestamps are ISO 8601 format (UTC).

---

## 🚀 Next Steps

1. ✅ **Read** this quick reference
2. ✅ **Import** postman_collection.json into Postman
3. ✅ **Test** endpoints against your local server
4. ✅ **Refer** to API_CONTRACT.md for detailed docs
5. ✅ **Share** feedback and issues

---

**API Version**: 0.1.0  
**Last Updated**: March 4, 2026  
**Status**: Active Development
