# TCGPlayer & eBay Sandbox Setup Guide

This guide walks you through setting up live pricing from TCGPlayer API and the eBay sandbox environment.

---

## 🎯 Quick Overview

| Service | Purpose | Status |
|---------|---------|--------|
| **TCGPlayer API** | Fetch live card prices | [Setup Required](#tcgplayer-api-setup) |
| **eBay Sandbox** | Test listing creation safely | [Setup Required](#ebay-sandbox-setup) |

---

## 1️⃣ TCGPlayer API Setup

### Step 1: Create TCGPlayer Developer Account

1. Go to https://tcgplayer.com
2. Create an account if you don't have one
3. Go to https://www.tcgplayer.com/account (Account Settings)
4. Look for "Developer" or "API" section
5. Request API access (may require contact with support)

### Step 2: Get Your API Credentials

You'll need:
- **Public Key** (API_KEY)
- **Private Key** (API_SECRET)

These look like:
```
Public Key:  abc123def456
Private Key: xyz789uvw012
```

### Step 3: Add to `.env` File

Open `mtg-inventory/.env` and add:

```bash
TCGPLAYER_API_KEY=your_public_key_here
TCGPLAYER_API_SECRET=your_private_key_here
```

Example:
```bash
TCGPLAYER_API_KEY=abc123def456
TCGPLAYER_API_SECRET=xyz789uvw012
```

### Step 4: Test Configuration

Run this command to verify:

```bash
cd mtg-inventory
python -c "
from services.tcgplayer_api import TCGPlayerAPI
api = TCGPlayerAPI()
token = api.get_auth_token()
if token:
    print('✓ TCGPlayer API authenticated!')
else:
    print('✗ Authentication failed - check credentials')
"
```

You should see: `✓ TCGPlayer API authenticated!`

### Step 5: Use in App

The dashboard will show "✓ Ready" for TCGPlayer API when configured.

**Refresh prices endpoint:**
```bash
curl -X POST http://localhost:5000/api/pricing/refresh
```

Response:
```json
{
  "success": true,
  "updated": 82,
  "failed": 0,
  "total": 100,
  "message": "Updated 82 card prices from TCGPlayer"
}
```

---

## 2️⃣ eBay Sandbox Setup

### Understanding eBay's OAuth Flow

eBay uses OAuth 2.0 with **refresh tokens**. You'll need:
- **Client ID** (from eBay Developer)
- **Client Secret** (from eBay Developer)
- **Refresh Token** (long-lived, typically expires after ~18 months unless revoked)

### Step 1: Create eBay Developer Account

1. Go to https://developer.ebay.com
2. Sign in or create an account
3. Go to https://developer.ebay.com/dashboard
4. Click "Create new app" or "Add app"

### Step 2: Get Application Keys

In your app settings, you'll see:
- **Client ID** (App ID)
- **Client Secret**

Copy these values - you'll need them.

### Step 3: Get Your Refresh Token

This is the trickiest part. eBay requires you to authorize once to get a long-lived refresh token.

**Option A: Using eBay's Auth Code Flow (Recommended)**

1. Open this URL in a browser (replace YOUR_CLIENT_ID):
```
https://auth.sandbox.ebay.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=https://localhost:3000&scope=https://api.ebay.com/oauth/api_scope
```

2. Click "Accept" when prompted
3. You'll be redirected to a URL with `code=...` in it
4. Copy that code

5. Run this script to exchange it for a refresh token:

```python
import requests
import base64

CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"
AUTH_CODE = "the_code_you_got_above"

credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

url = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
headers = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/x-www-form-urlencoded"
}
data = {
    "grant_type": "authorization_code",
    "code": AUTH_CODE,
    "redirect_uri": "https://localhost:3000"
}

response = requests.post(url, headers=headers, data=data)
result = response.json()

print("Refresh Token:", result.get('refresh_token'))
print("Access Token:", result.get('access_token'))
print("Expires in:", result.get('expires_in'), "seconds")
```

This will output your **refresh_token**. Save this value.

**Option B: Using cURL** (Alternative)

```bash
curl -X POST https://api.sandbox.ebay.com/identity/v1/oauth2/token \
  -H "Authorization: Basic [base64(CLIENT_ID:CLIENT_SECRET)]" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code&code=AUTHORIZATION_CODE&redirect_uri=https://localhost:3000"
```

### Step 4: Add to `.env` File

Open `mtg-inventory/.env` and add:

```bash
EBAY_CLIENT_ID=your_client_id_here
EBAY_CLIENT_SECRET=your_client_secret_here
EBAY_REFRESH_TOKEN=your_refresh_token_here
EBAY_SANDBOX_MODE=True
```

Example:
```bash
EBAY_CLIENT_ID=MyAppId-dev
EBAY_CLIENT_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
EBAY_REFRESH_TOKEN=v^1.1#i^1#p^3#f^0#...
EBAY_SANDBOX_MODE=True
```

### Step 5: Test Configuration

Run this command to verify:

```bash
cd mtg-inventory
python -c "
from services.ebay_api import eBayAPI
api = eBayAPI()
token = api.get_access_token()
if token:
    print('✓ eBay Sandbox authenticated!')
    print('Token:', token[:20] + '...')
else:
    print('✗ Authentication failed - check credentials')
"
```

You should see: `✓ eBay Sandbox authenticated!`

### Step 6: Use in App

The dashboard will show "✓ Ready (sandbox mode)" when configured.

---

## 🧪 Testing Both APIs

### Test TCGPlayer Pricing

```bash
# Refresh all card prices
curl -X POST http://localhost:5000/api/pricing/refresh

# Get pricing for a specific card
curl http://localhost:5000/api/pricing/{scryfall_id}
```

### Test eBay Listing Creation

```bash
# Create a draft listing (requires auth)
curl -X POST http://localhost:5000/api/ebay/listings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "title": "Black Lotus MTG LEA",
    "description": "Excellent condition",
    "price": 1200.00,
    "quantity": 1
  }'
```

---

## 🔧 Troubleshooting

### TCGPlayer Issues

**Error: "TCGPlayer API not configured"**
- Check that `TCGPLAYER_API_KEY` and `TCGPLAYER_API_SECRET` are set in `.env`
- Restart Flask server after editing `.env`
- Verify credentials at https://tcgplayer.com/account

**Error: "Product not found"**
- TCGPlayer may not have the card in inventory
- Try searching with just the card name
- Some special cards may not be available

**No prices returned**
- Wait a moment - first request may take 10+ seconds
- Check that card has pricing in TCGPlayer database

### eBay Issues

**Error: "Invalid client credentials"**
- Double-check CLIENT_ID and CLIENT_SECRET match exactly
- Make sure you're using sandbox credentials (not production)
- No extra spaces in credentials

**Error: "Invalid refresh_token"**
- Refresh tokens expire after 18 months
- Get a new one following Step 3 above
- Make sure you copied the entire token (may be very long)

**Error: "Access denied"**
- Check that scopes include `https://api.ebay.com/oauth/api_scope`
- May need to accept eBay's terms again

**Listing not created**
- Try with simpler data first
- Check eBay sandbox requirements for required fields
- Review output error message for specifics

---

## 📚 Documentation Links

**TCGPlayer:**
- API Docs: https://docs.tcgplayer.com
- Pricing: https://docs.tcgplayer.com/docs/pricing-api
- Product Search: https://docs.tcgplayer.com/docs/catalog-api

**eBay:**
- Dev Dashboard: https://developer.ebay.com
- OAuth Flow: https://developer.ebay.com/api-docs/identity/oauth-authorize-api/overview.html
- Inventory API: https://developer.ebay.com/api-docs/sell/inventory/overview.html
- Sandbox: https://sandbox.ebay.com

---

## 🚀 Running the App with APIs Configured

```bash
cd mtg-inventory

# Start Flask
python app.py

# Open browser
http://localhost:5000

# Check System Status section - should show ✓ for both APIs
```

---

## 💡 Next Steps

Once configured:

1. **Refresh Prices**: `POST /api/pricing/refresh` to update all card prices
2. **Create Listings**: Use `/api/ebay/listings` to list cards
3. **Monitor**: Dashboard shows real API status
4. **Scale**: Both APIs support rate limiting and pagination

---

## ❓ Questions?

- **TCGPlayer Help**: https://support.tcgplayer.com
- **eBay Help**: https://developer.ebay.com/support
- Check `/api/dashboard/system-status` endpoint for current status

---

**Last Updated:** March 5, 2026  
**API Version:** 0.1.0
