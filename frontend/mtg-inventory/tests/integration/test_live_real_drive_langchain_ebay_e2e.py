"""Live end-to-end validation using real external services (no mocks)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import app as app_module
from config import Config
from models import Card


def _required_env_missing() -> list[str]:
    required = [
        "LIVE_E2E_IMAGE_PATH",
        "GOOGLE_DRIVE_CREDENTIALS_JSON",
    ]
    missing = [key for key in required if not os.getenv(key)]

    if not (Config.EBAY_USER_TOKEN or (Config.EBAY_CLIENT_ID and Config.EBAY_CLIENT_SECRET and Config.EBAY_REFRESH_TOKEN)):
        missing.append("EBAY auth credentials")

    return missing


@pytest.mark.integration
@pytest.mark.slow
def test_live_drive_langchain_db_ebay_e2e_no_mocks():
    """Upload -> scan -> import -> search -> draft -> publish -> db verify with real APIs."""
    missing = _required_env_missing()
    if missing:
        pytest.skip(f"Live e2e prerequisites missing: {', '.join(missing)}")

    if not Config.EBAY_SANDBOX_MODE:
        pytest.skip("Refusing to run live listing test when EBAY_SANDBOX_MODE is not true")

    image_path = Path(os.getenv("LIVE_E2E_IMAGE_PATH", "")).expanduser().resolve()
    if not image_path.exists():
        pytest.skip(f"LIVE_E2E_IMAGE_PATH not found: {image_path}")

    min_confidence = os.getenv("LIVE_E2E_MIN_CONFIDENCE", "0.90")
    expected_card_name = os.getenv("LIVE_E2E_EXPECTED_CARD_NAME", "Erratic Visionary").strip()
    folder_url = os.getenv("GOOGLE_DRIVE_TARGET_FOLDER_URL", "")

    app_module.app.config["TESTING"] = True

    with app_module.app.test_client() as client:
        with image_path.open("rb") as f:
            payload = {
                "file": (f, image_path.name),
                "min_confidence": min_confidence,
            }
            if folder_url:
                payload["folder_url"] = folder_url

            scan_resp = client.post(
                "/api/integrations/google-drive/scan-import",
                data=payload,
                content_type="multipart/form-data",
            )

        assert scan_resp.status_code == 200, scan_resp.get_json()
        scan_data = scan_resp.get_json()
        assert scan_data["success"] is True

        scanner = scan_data["result"]["scanner"]
        assert scanner["status"] == "success"
        assert float(scanner["confidence"]) >= float(scanner["required_confidence"])

        card_name = (scanner.get("card_name") or "").strip()
        assert card_name
        assert card_name.lower() == expected_card_name.lower(), (
            f"Expected scan card '{expected_card_name}', got '{card_name}'"
        )

        # Verify frontend DB visibility via search API
        query = card_name.split()[0]
        search_resp = client.get(f"/api/cards/search?q={query}")
        assert search_resp.status_code == 200
        matches = search_resp.get_json()
        assert isinstance(matches, list)
        assert matches, f"No cards visible via search for query '{query}'"

        selected = next((item for item in matches if item.get("name") == card_name), matches[0])
        card_id = int(selected["id"])

        # Create eBay draft listing
        draft_resp = client.post(
            "/api/ebay/listings",
            json={"card_id": card_id, "force_new_offer": True},
        )
        assert draft_resp.status_code == 200, draft_resp.get_json()
        draft_data = draft_resp.get_json()
        assert draft_data["success"] is True
        assert draft_data.get("offer_id")

        # Publish listing to eBay
        publish_resp = None
        publish_data = None
        publish_attempts = int(os.getenv("LIVE_E2E_PUBLISH_ATTEMPTS", "5"))
        publish_delay = float(os.getenv("LIVE_E2E_PUBLISH_DELAY_SECONDS", "3"))
        for attempt in range(publish_attempts):
            publish_resp = client.post(f"/api/ebay/cards/{card_id}/publish")
            publish_data = publish_resp.get_json()
            if publish_resp.status_code == 200:
                break
            if attempt < publish_attempts - 1:
                time.sleep(publish_delay * (attempt + 1))

        assert publish_resp is not None
        assert publish_resp.status_code == 200, publish_data
        assert publish_data["success"] is True
        assert publish_data.get("listing_id")

    # Verify persisted listing IDs in DB
    db = app_module.SessionLocal()
    try:
        card = db.query(Card).filter(Card.id == card_id).first()
        assert card is not None
        assert card.ebay_offer_id
        assert card.ebay_listing_id
    finally:
        db.close()
