# MTG Inventory API Contract v0.1.0

## Overview

This document defines the complete API contract for the MTG Inventory System. All endpoints follow RESTful conventions with JSON request/response bodies.

**Base URL**: `http://localhost:5000` (development) | `https://api.mtg-inventory.com` (production)

**API Version**: `0.1.0`

**Last Updated**: March 4, 2026

---

## 📋 Table of Contents

1. [Authentication](#authentication)
2. [Common Headers & Conventions](#common-headers--conventions)
3. [Error Handling](#error-handling)
4. [Status Codes](#status-codes)
5. [Endpoints by Resource](#endpoints-by-resource)
   - [Health & System](#health--system)
   - [Cards](#cards)
   - [Inventory Management](#inventory-management)
   - [Locations & Boxes](#locations--boxes)
   - [Pricing](#pricing)
   - [eBay Integration](#ebay-integration)
6. [Data Models](#data-models)
7. [Examples](#examples)

---

## Authentication

### Bearer Token (Future Implementation)

The API will use Bearer token authentication for protected endpoints.

```http
Authorization: Bearer <token>
```

**Current Status**: Not yet implemented. All endpoints are publicly accessible for testing.

### API Key Alternative (Future)

Alternative authentication via query parameter:

```
GET /api/endpoint?api_key=<key>
```

---

## Common Headers & Conventions

### Request Headers

All requests to API endpoints should include:

```http
Content-Type: application/json
Accept: application/json
User-Agent: MTGInventory-Client/1.0
```

### Response Headers

All responses include:

```http
Content-Type: application/json; charset=utf-8
X-API-Version: 0.1.0
X-Response-Time: <milliseconds>
Cache-Control: no-cache
```

### Request/Response Format

All JSON bodies use:
- **Field naming**: `snake_case` for JSON keys
- **Timestamps**: ISO 8601 format (e.g., `2026-03-04T15:30:00Z`)
- **Numbers**: Floats with 2 decimal places for currency
- **Booleans**: JSON boolean values (`true`/`false`)
- **Null values**: Explicitly represented as `null`

---

## Error Handling

### Error Response Format

All errors return a standardized error object:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested card does not exist",
    "status": 404,
    "timestamp": "2026-03-04T15:30:00Z",
    "request_id": "req_abc123xyz",
    "details": {
      "field": "card_id",
      "value": "999"
    }
  }
}
```

### Error Codes

| Code | Meaning | HTTP Status |
|------|---------|------------|
| `INVALID_REQUEST` | Malformed request | 400 |
| `INVALID_FIELD` | Field validation failed | 400 |
| `RESOURCE_NOT_FOUND` | Resource doesn't exist | 404 |
| `RESOURCE_CONFLICT` | Duplicate resource | 409 |
| `UNAUTHORIZED` | Missing/invalid auth | 401 |
| `FORBIDDEN` | Insufficient permissions | 403 |
| `RATE_LIMITED` | Too many requests | 429 |
| `SERVER_ERROR` | Internal error | 500 |
| `SERVICE_UNAVAILABLE` | Service down | 503 |

---

## Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| `200` | OK | Successful GET/PUT request |
| `201` | Created | Successful POST that creates resource |
| `202` | Accepted | Long-running operation queued |
| `204` | No Content | Successful DELETE with no body |
| `400` | Bad Request | Invalid parameters or malformed body |
| `401` | Unauthorized | Missing/invalid authentication |
| `403` | Forbidden | Valid auth but insufficient permissions |
| `404` | Not Found | Resource doesn't exist |
| `409` | Conflict | Duplicate or conflicting resource |
| `429` | Too Many Requests | Rate limited |
| `500` | Internal Server Error | Server-side error |
| `503` | Service Unavailable | Temporary service issue |

---

## Endpoints by Resource

---

### Health & System

#### GET /api/health

**Description**: Health check endpoint. Use to verify API is online.

**Authentication**: Not required

**Headers**:
```http
GET /api/health HTTP/1.1
Host: localhost:5000
Accept: application/json
```

**Request Body**: None

**Response**:
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "ok",
  "database": "connected",
  "version": "0.1.0",
  "timestamp": "2026-03-04T15:30:00Z",
  "uptime_seconds": 3600
}
```

**Status Codes**:
- `200 OK` - System is healthy
- `503 Service Unavailable` - Database or critical service down

**Example**:
```bash
curl -X GET http://localhost:5000/api/health
```

---

### Cards

#### GET /api/cards/search

**Description**: Search for cards by name, set, or condition.

**Authentication**: Not required

**Query Parameters**:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `q` | string | Yes | Search query (min 2 chars) | `Ragavan` |
| `limit` | integer | No | Result limit (max 100) | `10` |
| `offset` | integer | No | Pagination offset | `0` |
| `set` | string | No | Filter by set code | `MH2` |
| `foil` | boolean | No | Filter by foil status | `true` |
| `condition` | string | No | Filter by condition | `NM` |
| `min_price` | float | No | Minimum price filter | `10.50` |
| `max_price` | float | No | Maximum price filter | `100.00` |

**Request**:
```http
GET /api/cards/search?q=Ragavan&limit=10&foil=false HTTP/1.1
Host: localhost:5000
Accept: application/json
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "scryfall_id": "uuid-1234",
      "name": "Ragavan, Nimble Pilferer",
      "set_code": "MH2",
      "set_name": "Modern Horizons 2",
      "collector_number": "138",
      "foil": false,
      "rarity": "rare",
      "condition": "NM",
      "market_price": 48.50,
      "quantity": 1,
      "location_code": "BOX-0001-SLOT-0001",
      "created_at": "2026-03-04T10:00:00Z",
      "updated_at": "2026-03-04T15:30:00Z"
    }
  ],
  "pagination": {
    "total": 1,
    "limit": 10,
    "offset": 0,
    "has_more": false
  }
}
```

**Error Response** (400 Bad Request):
```json
{
  "error": {
    "code": "INVALID_FIELD",
    "message": "Search query must be at least 2 characters",
    "status": 400,
    "timestamp": "2026-03-04T15:30:00Z"
  }
}
```

**Status Codes**:
- `200 OK` - Success (may return empty results)
- `400 Bad Request` - Invalid query parameters
- `401 Unauthorized` - Authentication required

**Examples**:
```bash
# Basic search
curl "http://localhost:5000/api/cards/search?q=Ragavan"

# Advanced search
curl "http://localhost:5000/api/cards/search?q=Dark&set=RAV&condition=LP&limit=20"

# Price range
curl "http://localhost:5000/api/cards/search?q=Tarmogoyf&min_price=10&max_price=50"
```

---

#### GET /api/cards/:id

**Description**: Get detailed information about a specific card.

**Authentication**: Not required

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | integer | Card database ID |

**Request**:
```http
GET /api/cards/1 HTTP/1.1
Host: localhost:5000
Accept: application/json
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "id": 1,
    "scryfall_id": "uuid-1234",
    "manabox_id": "MH2_138",
    "name": "Ragavan, Nimble Pilferer",
    "set_code": "MH2",
    "set_name": "Modern Horizons 2",
    "collector_number": "138",
    "foil": false,
    "rarity": "rare",
    "quantity": 1,
    "condition": "NM",
    "language": "en",
    "purchase_price": 45.00,
    "location_code": "BOX-0001-SLOT-0001",
    "box_number": 1,
    "slot_number": 1,
    "list_on_ebay": true,
    "ebay_listing_id": "ebay_123456",
    "tcgplayer_product_id": "tcg_999",
    "prices": {
      "market_price": 48.50,
      "low_price": 45.00,
      "high_price": 65.00,
      "fetched_at": "2026-03-04T10:00:00Z"
    },
    "created_at": "2026-03-04T10:00:00Z",
    "updated_at": "2026-03-04T15:30:00Z"
  }
}
```

**Error Response** (404 Not Found):
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Card with ID 999 not found",
    "status": 404,
    "timestamp": "2026-03-04T15:30:00Z"
  }
}
```

**Status Codes**:
- `200 OK` - Card found
- `404 Not Found` - Card doesn't exist

**Example**:
```bash
curl http://localhost:5000/api/cards/1
```

---

#### GET /api/cards

**Description**: List all cards with pagination and filtering.

**Authentication**: Not required

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | `50` | Records per page (max 100) |
| `offset` | integer | `0` | Pagination offset |
| `sort` | string | `created_at` | Sort field |
| `order` | string | `desc` | Sort order (asc/desc) |
| `foil` | boolean | - | Filter by foil status |
| `listed` | boolean | - | Filter by eBay listing status |

**Request**:
```http
GET /api/cards?limit=20&offset=0&sort=name&order=asc HTTP/1.1
Host: localhost:5000
Accept: application/json
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": [
    { "id": 1, "name": "Ragavan...", "..." : "..." },
    { "id": 2, "name": "Wrenn...", "..." : "..." }
  ],
  "pagination": {
    "total": 2847,
    "limit": 20,
    "offset": 0,
    "has_more": true,
    "pages": 143
  }
}
```

**Status Codes**:
- `200 OK` - Success

---

### Inventory Management

#### POST /inventory/import

**Description**: Upload and import a CSV file of cards from ManaBox.

**Authentication**: Not required (currently)

**Content-Type**: `multipart/form-data`

**Request**:
```http
POST /inventory/import HTTP/1.1
Host: localhost:5000
Content-Type: multipart/form-data

file=<CSV_FILE_BINARY>
```

**CSV Format Expected**:
```csv
name,set,number,condition,foil,quantity
"Ragavan, Nimble Pilferer",MH2,138,NM,normal,1
"Wrenn and Six",MH1,217,LP,foil,1
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "filename": "manabox_export.csv",
    "added": 342,
    "updated": 45,
    "skipped": 12,
    "errors": 0,
    "total_processed": 399,
    "processing_time_ms": 2350
  },
  "message": "Import successful: 342 added, 45 updated, 12 skipped"
}
```

**Error Response** (400 Bad Request):
```json
{
  "error": {
    "code": "INVALID_FILE",
    "message": "File must be a CSV file",
    "status": 400,
    "timestamp": "2026-03-04T15:30:00Z"
  }
}
```

**Status Codes**:
- `200 OK` - Import completed (check stats for actual success)
- `400 Bad Request` - Invalid file type or format
- `500 Internal Server Error` - Processing error

**Examples**:
```bash
# Using curl
curl -X POST -F "file=@export.csv" http://localhost:5000/inventory/import

# Using Python requests
import requests
with open('export.csv', 'rb') as f:
    files = {'file': f}
    resp = requests.post('http://localhost:5000/inventory/import', files=files)
```

---

#### PUT /api/cards/:id

**Description**: Update a card's information.

**Authentication**: Bearer token required

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | integer | Card ID |

**Request**:
```http
PUT /api/cards/1 HTTP/1.1
Host: localhost:5000
Authorization: Bearer <token>
Content-Type: application/json

{
  "condition": "LP",
  "foil": true,
  "quantity": 2,
  "purchase_price": 45.00,
  "list_on_ebay": true
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "Ragavan, Nimble Pilferer",
    "condition": "LP",
    "foil": true,
    "quantity": 2,
    "purchase_price": 45.00,
    "list_on_ebay": true,
    "updated_at": "2026-03-04T15:35:00Z"
  }
}
```

**Status Codes**:
- `200 OK` - Update successful
- `400 Bad Request` - Invalid field values
- `404 Not Found` - Card not found
- `401 Unauthorized` - Missing auth token

---

#### DELETE /api/cards/:id

**Description**: Delete a card from inventory.

**Authentication**: Bearer token required (admin)

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | integer | Card ID |

**Request**:
```http
DELETE /api/cards/1 HTTP/1.1
Host: localhost:5000
Authorization: Bearer <token>
```

**Response** (204 No Content):
```http
HTTP/1.1 204 No Content
```

**Status Codes**:
- `204 No Content` - Deletion successful
- `404 Not Found` - Card not found
- `401 Unauthorized` - Missing auth token
- `403 Forbidden` - Insufficient permissions

---

### Locations & Boxes

#### GET /api/boxes

**Description**: Get all storage boxes with statistics.

**Authentication**: Not required

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `include_cards` | boolean | Include card list in response |
| `limit` | integer | Max boxes (for pagination) |
| `offset` | integer | Pagination offset |

**Request**:
```http
GET /api/boxes?include_cards=false HTTP/1.1
Host: localhost:5000
Accept: application/json
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "number": 1,
      "capacity": 500,
      "current_count": 500,
      "fill_percentage": 100,
      "qr_code_url": "/qrcodes/BOX-0001.png",
      "created_at": "2026-03-04T10:00:00Z"
    },
    {
      "id": 2,
      "number": 2,
      "capacity": 500,
      "current_count": 487,
      "fill_percentage": 97.4,
      "qr_code_url": "/qrcodes/BOX-0002.png",
      "created_at": "2026-03-04T10:05:00Z"
    }
  ],
  "statistics": {
    "total_boxes": 2,
    "total_capacity": 1000,
    "total_cards": 987,
    "average_fill": 98.7
  }
}
```

**Status Codes**:
- `200 OK` - Success

---

#### GET /api/boxes/:id

**Description**: Get details for a specific box including all cards.

**Authentication**: Not required

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | integer | Box ID |

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Cards per page (default 50) |
| `offset` | integer | Pagination offset |
| `sort` | string | Sort field (name, slot, created_at) |

**Request**:
```http
GET /api/boxes/1?limit=20&offset=0&sort=slot HTTP/1.1
Host: localhost:5000
Accept: application/json
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "id": 1,
    "number": 1,
    "capacity": 500,
    "current_count": 500,
    "fill_percentage": 100,
    "qr_code_url": "/qrcodes/BOX-0001.png",
    "cards": [
      {
        "id": 1,
        "name": "Ragavan, Nimble Pilferer",
        "slot_number": 1,
        "location_code": "BOX-0001-SLOT-0001",
        "condition": "NM",
        "foil": false,
        "market_price": 48.50
      },
      {
        "id": 2,
        "name": "Wrenn and Six",
        "slot_number": 2,
        "location_code": "BOX-0001-SLOT-0002",
        "condition": "LP",
        "foil": true,
        "market_price": 32.00
      }
    ],
    "pagination": {
      "total": 500,
      "limit": 20,
      "offset": 0,
      "has_more": true
    }
  }
}
```

**Error Response** (404 Not Found):
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Box with ID 99 not found",
    "status": 404,
    "timestamp": "2026-03-04T15:30:00Z"
  }
}
```

**Status Codes**:
- `200 OK` - Box found
- `404 Not Found` - Box doesn't exist

---

#### POST /api/boxes/:id/qr

**Description**: Generate a QR code image for a box.

**Authentication**: Bearer token required

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | integer | Box ID |

**Request**:
```http
POST /api/boxes/1/qr HTTP/1.1
Host: localhost:5000
Authorization: Bearer <token>
Content-Type: application/json
```

**Response** (201 Created):
```json
{
  "success": true,
  "data": {
    "id": 1,
    "qr_code_url": "/qrcodes/BOX-0001.png",
    "generated_at": "2026-03-04T15:30:00Z"
  }
}
```

**Status Codes**:
- `201 Created` - QR code generated
- `404 Not Found` - Box not found
- `409 Conflict` - QR code already exists

---

### Pricing

#### GET /api/pricing/:scryfall_id

**Description**: Get current market pricing for a card from TCGPlayer.

**Authentication**: Not required

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `scryfall_id` | string | Scryfall ID (UUID format) |

**Request**:
```http
GET /api/pricing/uuid-1234?condition=NM HTTP/1.1
Host: localhost:5000
Accept: application/json
```

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `condition` | string | Card condition filter |

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "scryfall_id": "uuid-1234",
    "card_name": "Ragavan, Nimble Pilferer",
    "prices": {
      "market_price": 48.50,
      "low_price": 45.00,
      "high_price": 65.00,
      "currency": "USD"
    },
    "conditions": {
      "NM": { "market": 48.50, "low": 45.00, "high": 65.00 },
      "LP": { "market": 41.23, "low": 38.00, "high": 55.00 },
      "MP": { "market": 33.18, "low": 30.00, "high": 45.00 },
      "HP": { "market": 24.25, "low": 20.00, "high": 32.00 },
      "PO": { "market": 14.55, "low": 10.00, "high": 20.00 }
    },
    "fetched_at": "2026-03-04T15:00:00Z"
  }
}
```

**Error Response** (404 Not Found):
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Pricing not available for this card",
    "status": 404,
    "timestamp": "2026-03-04T15:30:00Z"
  }
}
```

**Status Codes**:
- `200 OK` - Pricing found
- `404 Not Found` - No pricing available

---

#### POST /api/pricing/refresh

**Description**: Refresh all currently cached prices from TCGPlayer (requires auth).

**Authentication**: Bearer token required

**Request**:
```http
POST /api/pricing/refresh HTTP/1.1
Host: localhost:5000
Authorization: Bearer <token>
Content-Type: application/json

{
  "limit": 100,
  "force": false
}
```

**Request Body**:
```json
{
  "limit": 100,
  "force": false
}
```

**Response** (202 Accepted):
```json
{
  "success": true,
  "message": "Price refresh queued",
  "data": {
    "job_id": "job_abc123",
    "cards_to_update": 2847,
    "estimated_time_seconds": 45,
    "status_url": "/api/pricing/refresh/job_abc123"
  }
}
```

**Status Codes**:
- `202 Accepted` - Refresh job queued
- `401 Unauthorized` - Missing auth token
- `429 Rate Limited` - Too many refresh requests

---

### eBay Integration

#### GET /api/ebay/listings

**Description**: Get all eBay listings linked to cards.

**Authentication**: Bearer token required

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status (draft, active, sold) |
| `limit` | integer | Results per page |
| `offset` | integer | Pagination offset |

**Request**:
```http
GET /api/ebay/listings?status=active&limit=20 HTTP/1.1
Host: localhost:5000
Authorization: Bearer <token>
Accept: application/json
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": [
    {
      "id": "ebay_123456",
      "card_id": 1,
      "card_name": "Ragavan, Nimble Pilferer",
      "title": "Ragavan, Nimble Pilferer MH2 MTG NM — Magic: The Gathering",
      "price": 52.99,
      "status": "active",
      "quantity": 1,
      "url": "https://www.ebay.com/itm/...",
      "created_at": "2026-03-04T10:00:00Z",
      "updated_at": "2026-03-04T15:30:00Z"
    }
  ],
  "pagination": {
    "total": 38,
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

**Status Codes**:
- `200 OK` - Success
- `401 Unauthorized` - Missing auth token

---

#### POST /api/ebay/listings

**Description**: Create a new eBay listing from a card.

**Authentication**: Bearer token required

**Request**:
```http
POST /api/ebay/listings HTTP/1.1
Host: localhost:5000
Authorization: Bearer <token>
Content-Type: application/json

{
  "card_id": 1,
  "price": 52.99,
  "quantity": 1,
  "condition_id": 3000,
  "category_id": "19476",
  "duration": 30,
  "auto_decline_below": 45.00,
  "shipping_type": "flat",
  "shipping_cost": 4.99,
  "return_days": 30
}
```

**Request Body Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `card_id` | integer | Yes | Card database ID |
| `price` | float | Yes | Listing price in USD |
| `quantity` | integer | Yes | Quantity available |
| `condition_id` | integer | Yes | eBay condition ID |
| `category_id` | string | Yes | eBay category ID |
| `duration` | integer | No | Listing duration in days (default 30) |
| `auto_decline_below` | float | No | Auto-decline offers below |
| `shipping_type` | string | No | flat/calculated (default flat) |
| `shipping_cost` | float | No | Fixed shipping cost |
| `return_days` | integer | No | Return period in days |

**Response** (201 Created):
```json
{
  "success": true,
  "data": {
    "id": "ebay_123456",
    "card_id": 1,
    "status": "active",
    "title": "Ragavan, Nimble Pilferer MH2 MTG NM — Magic: The Gathering",
    "price": 52.99,
    "url": "https://www.ebay.com/itm/123456789",
    "created_at": "2026-03-04T15:30:00Z"
  }
}
```

**Error Response** (400 Bad Request):
```json
{
  "error": {
    "code": "INVALID_FIELD",
    "message": "Price must be greater than 0",
    "status": 400,
    "timestamp": "2026-03-04T15:30:00Z",
    "details": {
      "field": "price",
      "value": -5.00
    }
  }
}
```

**Status Codes**:
- `201 Created` - Listing created
- `400 Bad Request` - Invalid parameters
- `401 Unauthorized` - Missing auth token
- `404 Not Found` - Card not found

---

#### PUT /api/ebay/listings/:id

**Description**: Update an eBay listing.

**Authentication**: Bearer token required

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | eBay listing ID |

**Request**:
```http
PUT /api/ebay/listings/ebay_123456 HTTP/1.1
Host: localhost:5000
Authorization: Bearer <token>
Content-Type: application/json

{
  "price": 49.99,
  "quantity": 0
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "id": "ebay_123456",
    "price": 49.99,
    "status": "ended",
    "updated_at": "2026-03-04T15:35:00Z"
  }
}
```

**Status Codes**:
- `200 OK` - Updated
- `404 Not Found` - Listing not found
- `401 Unauthorized` - Missing auth token

---

#### DELETE /api/ebay/listings/:id

**Description**: End/delete an eBay listing.

**Authentication**: Bearer token required

**Path Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | eBay listing ID |

**Request**:
```http
DELETE /api/ebay/listings/ebay_123456 HTTP/1.1
Host: localhost:5000
Authorization: Bearer <token>
```

**Response** (204 No Content):
```http
HTTP/1.1 204 No Content
```

**Status Codes**:
- `204 No Content` - Deleted
- `404 Not Found` - Listing not found
- `401 Unauthorized` - Missing auth token

---

## Data Models

### Card Object

```json
{
  "id": 1,
  "scryfall_id": "uuid-string",
  "manabox_id": "string",
  "name": "Card Name",
  "set_code": "MH2",
  "set_name": "Modern Horizons 2",
  "collector_number": "138",
  "foil": false,
  "rarity": "rare",
  "quantity": 1,
  "condition": "NM",
  "language": "en",
  "purchase_price": 45.00,
  "location_code": "BOX-0001-SLOT-0001",
  "box_number": 1,
  "slot_number": 1,
  "list_on_ebay": true,
  "ebay_listing_id": "ebay_123456",
  "tcgplayer_product_id": "tcg_999",
  "created_at": "2026-03-04T10:00:00Z",
  "updated_at": "2026-03-04T15:30:00Z"
}
```

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | integer | Yes | Unique database ID |
| `scryfall_id` | string | Yes | Scryfall UUID (unique) |
| `manabox_id` | string | No | ManaBox ID |
| `name` | string | Yes | Card name |
| `set_code` | string | Yes | Magic set code (MH2, INN, etc.) |
| `set_name` | string | No | Full set name |
| `collector_number` | string | Yes | Card number in set |
| `foil` | boolean | No | Is foil variant (default false) |
| `rarity` | string | No | Card rarity (common, uncommon, rare, mythic) |
| `quantity` | integer | No | Quantity in inventory (default 1) |
| `condition` | string | Yes | Condition (NM, LP, MP, HP, PO) |
| `language` | string | No | Card language (default en) |
| `purchase_price` | float | No | What you paid for it |
| `location_code` | string | No | Box/slot location |
| `box_number` | integer | No | Storage box number |
| `slot_number` | integer | No | Slot in box |
| `list_on_ebay` | boolean | No | Is listed on eBay (default false) |
| `ebay_listing_id` | string | No | eBay item number |
| `tcgplayer_product_id` | string | No | TCGPlayer product ID |
| `created_at` | timestamp | Auto | Creation time |
| `updated_at` | timestamp | Auto | Last update time |

---

### Box Object

```json
{
  "id": 1,
  "number": 1,
  "capacity": 500,
  "current_count": 500,
  "fill_percentage": 100,
  "qr_code_url": "/qrcodes/BOX-0001.png",
  "created_at": "2026-03-04T10:00:00Z"
}
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique box ID |
| `number` | integer | Box number (1, 2, 3...) |
| `capacity` | integer | Max cards per box |
| `current_count` | integer | Cards currently in box |
| `fill_percentage` | float | (current_count / capacity) * 100 |
| `qr_code_url` | string | URL to QR code image |
| `created_at` | timestamp | Box creation time |

---

### Price Object

```json
{
  "scryfall_id": "uuid-string",
  "market_price": 48.50,
  "low_price": 45.00,
  "high_price": 65.00,
  "currency": "USD",
  "fetched_at": "2026-03-04T15:00:00Z"
}
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `scryfall_id` | string | Card's Scryfall ID |
| `market_price` | float | Current market price |
| `low_price` | float | Lowest recent price |
| `high_price` | float | Highest recent price |
| `currency` | string | Currency code (USD) |
| `fetched_at` | timestamp | When price was fetched |

---

### eBay Listing Object

```json
{
  "id": "ebay_123456",
  "card_id": 1,
  "card_name": "Ragavan, Nimble Pilferer",
  "title": "Ragavan, Nimble Pilferer MH2 MTG NM — Magic: The Gathering",
  "description": "NM condition, non-foil...",
  "price": 52.99,
  "status": "active",
  "quantity": 1,
  "condition_id": 3000,
  "url": "https://www.ebay.com/itm/123456789",
  "created_at": "2026-03-04T10:00:00Z",
  "updated_at": "2026-03-04T15:30:00Z"
}
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | eBay item/listing ID |
| `card_id` | integer | Linked card ID |
| `card_name` | string | Card name |
| `title` | string | eBay listing title |
| `description` | string | eBay listing description |
| `price` | float | Current listing price |
| `status` | string | active, ended, draft, sold |
| `quantity` | integer | Quantity available |
| `condition_id` | integer | eBay condition ID |
| `url` | string | Link to eBay listing |
| `created_at` | timestamp | When listing was created |
| `updated_at` | timestamp | Last update time |

---

## Examples

### Full Workflow Example: Import and List Card

#### Step 1: Import CSV
```bash
curl -X POST \
  -F "file=@cards.csv" \
  http://localhost:5000/inventory/import
```

Response:
```json
{
  "success": true,
  "data": {
    "added": 342,
    "updated": 0,
    "skipped": 0,
    "errors": 0
  }
}
```

#### Step 2: Search for Imported Card
```bash
curl "http://localhost:5000/api/cards/search?q=Ragavan&limit=1"
```

Response:
```json
{
  "data": [{
    "id": 1,
    "name": "Ragavan, Nimble Pilferer",
    "scryfall_id": "uuid-1234",
    "location_code": "BOX-0001-SLOT-0001"
  }]
}
```

#### Step 3: Get Card Pricing
```bash
curl "http://localhost:5000/api/pricing/uuid-1234?condition=NM"
```

Response:
```json
{
  "data": {
    "market_price": 48.50,
    "low_price": 45.00,
    "high_price": 65.00
  }
}
```

#### Step 4: Create eBay Listing (requires auth)
```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "card_id": 1,
    "price": 52.99,
    "quantity": 1,
    "condition_id": 3000
  }' \
  http://localhost:5000/api/ebay/listings
```

Response:
```json
{
  "success": true,
  "data": {
    "id": "ebay_123456",
    "status": "active",
    "url": "https://www.ebay.com/itm/..."
  }
}
```

---

## Authentication (Future Implementation)

### Obtaining a Token

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password"
  }' \
  http://localhost:5000/auth/login
```

Response:
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 86400,
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

### Using the Token

```bash
curl -X GET \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  http://localhost:5000/api/ebay/listings
```

---

## Rate Limiting (Future Implementation)

The API will enforce rate limits:

**Headers included in all responses**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1646398200
```

**When limit exceeded (429 Too Many Requests)**:
```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded. Try again in 60 seconds.",
    "status": 429,
    "retry_after": 60
  }
}
```

---

## Changelog

### v0.1.0 (2026-03-04)
- ✅ Initial API contract created
- ✅ Health check endpoint
- ✅ Card search endpoint
- ✅ CSV import endpoint
- ✅ Box listing endpoints
- ✅ Pricing endpoints (stub)
- ✅ eBay integration (stub)
- ⏳ Authentication (planned)
- ⏳ Rate limiting (planned)

---

## Support & Questions

For API questions or issues:

1. **Check this contract** - Most answers are here
2. **Check logs** - Review Flask terminal output
3. **Check status** - Hit `/api/health` to verify service
4. **Check tests** - Review test files for working examples

---

**Last Updated**: March 4, 2026  
**Maintained By**: MTG Inventory Team  
**Version**: 0.1.0
