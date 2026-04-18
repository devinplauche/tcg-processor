# 📚 API Documentation Index

## Overview

Complete API documentation has been created for the MTG Inventory System in multiple formats to support different workflows and tools.

---

## 📑 Documentation Files

### 1. **API_CONTRACT.md** - Comprehensive Specification
**Type**: Markdown  
**Purpose**: Human-readable, complete specification with examples  
**Best For**: Developers, API users, understanding the full scope  
**Contents**:
- Authentication & authorization
- Common headers & conventions
- Error handling & status codes
- All endpoints with detailed descriptions
- Request/response examples
- Data models & schemas
- Full workflow examples

**Use This When**: You need complete details about an endpoint, understanding errors, or full context

---

### 2. **openapi.yaml** - Standardized Machine-Readable Spec
**Type**: OpenAPI 3.0 / Swagger  
**Purpose**: Standard format for API documentation tools  
**Best For**: Tool integration, documentation generation, automation  
**Contents**:
- All endpoints in OpenAPI format
- Request/response schemas
- Parameter definitions
- Status codes & error responses
- Security schemes
- Tag organization

**Use This When**: Integrating with Swagger UI, ReDoc, code generators, or automated tools

**How to Use**:
1. **Swagger UI**: Visit https://editor.swagger.io → File → Import
2. **ReDoc**: Use `npx redoc-cli serve openapi.yaml`
3. **Code Generation**: `openapi-generator` to auto-generate client SDKs

---

### 3. **postman_collection.json** - Ready-to-Test Requests
**Type**: Postman Collection v2.1  
**Purpose**: Interactive API testing  
**Best For**: Testing endpoints, development, QA  
**Contents**:
- 20+ pre-configured requests
- All HTTP methods (GET, POST, PUT, DELETE)
- Request/response examples
- Query parameters & headers
- Variables for base URL & auth token
- Organized by resource

**Use This When**: Testing API endpoints, debugging, manual QA

**How to Use**:
1. Download [Postman](https://www.postman.com/downloads/)
2. Click **Import** → Choose file → Select `postman_collection.json`
3. Set `{{base_url}}` variable to `http://localhost:5000`
4. Click any request and click **Send**

---

### 4. **API_QUICK_REFERENCE.md** - Developer Quick Start
**Type**: Markdown (condensed)  
**Purpose**: Quick lookup reference  
**Best For**: Developers, cheat sheet, common tasks  
**Contents**:
- Quick links to all documentation
- Common endpoints at a glance
- cURL examples
- Status codes table
- Query parameters reference
- Data field descriptions
- Debugging tips
- FAQ

**Use This When**: You need a quick answer, command examples, or common patterns

---

## 🎯 Which File to Use?

### "I want to understand the complete API"
→ Read **API_CONTRACT.md** from top to bottom

### "I want to quickly test endpoints"
→ Import **postman_collection.json** into Postman

### "I want to auto-generate client code"
→ Use **openapi.yaml** with code generators

### "I need a quick answer about endpoints"
→ Check **API_QUICK_REFERENCE.md**

### "I want to visualize the API"
→ Import **openapi.yaml** into Swagger UI or ReDoc

### "I'm integrating with external tools"
→ Use **openapi.yaml** for tool integration

---

## 📊 API Structure

### By Resource Type

**System**
- `GET /api/health` - Health check

**Cards**
- `GET /api/cards/search?q=...` - Search cards
- `GET /api/cards` - List all cards
- `GET /api/cards/{id}` - Get card details
- `PUT /api/cards/{id}` - Update card
- `DELETE /api/cards/{id}` - Delete card

**Inventory Management**
- `POST /inventory/import` - Upload CSV

**Locations (Boxes)**
- `GET /api/boxes` - List boxes
- `GET /api/boxes/{id}` - Get box details
- `POST /api/boxes/{id}/qr` - Generate QR code

**Pricing**
- `GET /api/pricing/{scryfall_id}` - Get pricing
- `POST /api/pricing/refresh` - Refresh prices

**eBay Integration**
- `GET /api/ebay/listings` - List listings
- `POST /api/ebay/listings` - Create listing
- `PUT /api/ebay/listings/{id}` - Update listing
- `DELETE /api/ebay/listings/{id}` - Delete listing

---

## 🔑 Key Concepts

### Authentication
- **Status**: Planned (not yet implemented)
- **Method**: Bearer token (JWT)
- **Header**: `Authorization: Bearer <token>`

### Response Format
All successful responses include:
```json
{
  "success": true,
  "data": { ... },
  "pagination": { ... }
}
```

All error responses include:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "status": 400,
    "timestamp": "2026-03-04T15:30:00Z"
  }
}
```

### Pagination
Supported on all list endpoints:
- `limit` - Records per page (default 50, max 100)
- `offset` - Skip records
- `sort` - Sort field
- `order` - asc/desc

### Status Codes
- `200` - Success
- `201` - Created
- `204` - No content (DELETE)
- `400` - Bad request
- `401` - Unauthorized
- `404` - Not found
- `500` - Server error

---

## 🚀 Quick Start

### Option 1: Postman (Recommended for Testing)
```
1. Download Postman
2. Import postman_collection.json
3. Set base_url to http://localhost:5000
4. Click requests and test
```

### Option 2: cURL (Command Line)
```bash
# Health check
curl http://localhost:5000/api/health

# Search cards
curl "http://localhost:5000/api/cards/search?q=Ragavan"

# List boxes
curl http://localhost:5000/api/boxes
```

### Option 3: Swagger UI (Visual)
```
1. Visit https://editor.swagger.io
2. File → Import → openapi.yaml
3. "Try it out" on any endpoint
```

---

## 📱 Integration Examples

### JavaScript/Node.js
```javascript
// Search cards
fetch('/api/cards/search?q=Ragavan')
  .then(r => r.json())
  .then(data => console.log(data))
```

### Python
```python
import requests
r = requests.get('http://localhost:5000/api/cards/search', 
                 params={'q': 'Ragavan'})
print(r.json())
```

### cURL
```bash
curl "http://localhost:5000/api/cards/search?q=Ragavan"
```

---

## ✅ Checklist for API Users

- [ ] Read API_QUICK_REFERENCE.md for overview
- [ ] Import postman_collection.json into Postman
- [ ] Test health endpoint: `GET /api/health`
- [ ] Try search endpoint: `GET /api/cards/search?q=test`
- [ ] Refer to API_CONTRACT.md for detailed docs
- [ ] Review API structure by resource type
- [ ] Understand response format & error handling
- [ ] Check status codes & error responses
- [ ] Set up authentication when implemented

---

## 🔄 Documentation Workflow

```
User Needs Answer
       ↓
Check API_QUICK_REFERENCE.md
       ↓
Found?
├─YES→ Use it
└─NO→ Check API_CONTRACT.md
       ↓
     Found?
     ├─YES→ Use it
     └─NO→ Open openapi.yaml in Swagger Editor
```

---

## 📦 File Locations

Documentation files are in `backend/contracts/`:

```
backend/
├── contracts/
│   ├── API_CONTRACT.md                  # Complete spec (main file)
│   ├── API_QUICK_REFERENCE.md           # Quick lookup
│   ├── openapi.yaml                     # OpenAPI specification
│   ├── postman_collection.json          # Postman requests
│   └── API_DOCUMENTATION_INDEX.md       # This file
├── app.py                               # Flask app
├── routes/
├── services/
├── templates/
└── static/
```

---

## 🔧 Tools Integration

### Swagger UI
```bash
# View API docs at http://localhost:8080
docker run -p 8080:8080 -v $(pwd)/openapi.yaml:/openapi.yaml \
  -e SWAGGER_JSON=/openapi.yaml swaggerapi/swagger-ui
```

### ReDoc
```bash
npx redoc-cli serve openapi.yaml
```

### Postman
1. File → Import → postman_collection.json
2. Done! Ready to test

### OpenAPI Code Generation
```bash
# Generate Python client
npm install @openapitools/openapi-generator-cli
npx openapi-generator-cli generate -i openapi.yaml \
  -g python -o ./client
```

---

## 📈 API Maturity

| Component | Status | Notes |
|-----------|--------|-------|
| Health & System | ✅ Ready | Fully implemented |
| Card Search | 🟡 Partial | Stub implemented, real Scryfall API pending |
| Card Management | ✅ Ready | Create, read, update, delete working |
| CSV Import | ✅ Ready | Full implementation with tests |
| Box Management | 🟡 Partial | Endpoints defined, QR code pending |
| Pricing | 🟡 Stub | Endpoint structure ready, TCGPlayer integration pending |
| eBay Integration | 🟡 Stub | Endpoints defined, real API integration pending |
| Authentication | 🔴 Not Started | Planned for Phase 2 |
| Rate Limiting | 🔴 Not Started | Planned for Phase 2 |

---

## 🐛 Known Issues

- Authentication not yet implemented (all endpoints public)
- Real API integrations are stubs (Scryfall, TCGPlayer, eBay)
- No rate limiting yet
- CORS not configured for external clients
- QR code generation not yet implemented

---

## 🔮 Coming Soon

- ✅ Phase 1: Documentation (DONE)
- 🚀 Phase 2: Authentication & rate limiting
- 🚀 Phase 3: Real API integrations
- 🚀 Phase 4: Advanced features (analytics, bulk operations)

---

## 📞 Support

**For API questions**:
1. Check API_QUICK_REFERENCE.md first
2. Search API_CONTRACT.md for details
3. Test in Postman using postman_collection.json
4. View openapi.yaml in Swagger Editor for interactive docs

**For code/implementation questions**:
- Review test files in `tests/` directory
- Check Flask app.py for endpoint implementations
- Review service files in `services/` directory

---

## 📝 Maintenance

This documentation is maintained alongside the API code.

**To update API docs**:
1. Edit API_CONTRACT.md with changes
2. Update openapi.yaml with OpenAPI spec changes
3. Update postman_collection.json requests
4. Update API_QUICK_REFERENCE.md with quick examples

---

**API Version**: 0.1.0  
**Last Updated**: March 4, 2026  
**Documentation Created**: March 4, 2026
