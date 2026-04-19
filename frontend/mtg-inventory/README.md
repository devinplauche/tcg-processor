## Live End-to-End (No Mocks)

This project now includes a real external-services workflow test:

- Upload file to Google Drive
- Scan card via LangChain (strict confidence gate)
- Import into Flask inventory database
- Verify card visibility through frontend search API
- Create eBay draft listing
- Publish eBay listing
- Verify persisted listing IDs in DB

### Required Environment

Set these in `.env.local`:

- `GOOGLE_DRIVE_CREDENTIALS_JSON` (supports both service account and installed OAuth JSON)
- `GOOGLE_DRIVE_TARGET_FOLDER_URL`
- `LANGCHAIN_SCANNER_ENDPOINT` (optional; leave empty to use local scanner script fallback)
- `LANGCHAIN_SCANNER_SCRIPT_PATH` (used by fallback mode)
- `LANGCHAIN_MIN_CONFIDENCE` (for strict gating)
- `EBAY_*` sandbox credentials
- `EBAY_AUTO_OPT_IN=true` (optional recovery attempt)

Also set:

- Live test image fixture is committed at `tests/integration/fixtures/live_e2e_card_image_from_drive.jpg`

### Run Live Test

```bash
python -m pytest -q tests/integration/test_live_real_drive_langchain_ebay_e2e.py --integration
```

### eBay Troubleshooting

If health reports missing policies or inventory not ready:

1. Check health: `GET /api/ebay/health`
2. Attempt opt-in: `GET /api/ebay/health?opt_in=1` or `POST /api/ebay/opt-in`
3. Run bootstrap: `POST /api/ebay/bootstrap`
4. Enable automation in `.env.local` for first-time sandbox setup:
`EBAY_AUTO_CREATE_LOCATION=true` and `EBAY_AUTO_CREATE_POLICIES=true`
5. If bootstrap still fails, set explicit `EBAY_PAYMENT_POLICY_ID`, `EBAY_FULFILLMENT_POLICY_ID`, `EBAY_RETURN_POLICY_ID`, and `EBAY_MERCHANT_LOCATION_KEY`.
6. If policy APIs remain empty for the account, switch to an inventory-enabled sandbox seller account.
