"""Strict end-to-end workflow tests for Drive upload -> LangChain scan -> DB -> eBay publish."""

from __future__ import annotations

import os
import sys
from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import app as app_module
from database import Base
from models import Card
from services.ebay_api import EbayListingState


@pytest.fixture
def e2e_client_and_session():
    """Provide a Flask client and isolated in-memory DB session factory."""
    app_module.app.config["TESTING"] = True

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    original_session_local = app_module.SessionLocal
    app_module.SessionLocal = TestSessionLocal

    try:
        with app_module.app.test_client() as client:
            yield client, TestSessionLocal
    finally:
        app_module.SessionLocal = original_session_local
        Base.metadata.drop_all(bind=engine)


def _mock_drive_and_scanner(mock_drive_cls, mock_scanner_cls, *, confidence: float) -> None:
    drive_instance = Mock()
    drive_instance.upload_file_bytes.return_value = {
        "id": "drive-file-123",
        "name": "scan.jpg",
        "webViewLink": "https://drive.google.com/file/d/drive-file-123/view",
    }
    drive_instance.download_file_bytes.return_value = b"fake-image-bytes"
    mock_drive_cls.return_value = drive_instance

    scanner_instance = Mock()
    scanner_instance.scan_image_bytes.return_value = {
        "status": "success",
        "card_name": "Path to Exile",
        "set_code": "2XM",
        "set_name": "Double Masters",
        "rarity": "rare",
        "confidence": confidence,
    }
    mock_scanner_cls.return_value = scanner_instance


@patch("services.google_drive_pipeline.LangChainScannerClient")
@patch("services.google_drive_pipeline.GoogleDriveClient")
def test_drive_scan_db_frontend_and_ebay_publish_strict_e2e(
    mock_drive_cls,
    mock_scanner_cls,
    e2e_client_and_session,
):
    """Upload to Drive, enforce high-confidence scan, verify frontend, then publish to eBay."""
    client, session_factory = e2e_client_and_session
    _mock_drive_and_scanner(mock_drive_cls, mock_scanner_cls, confidence=0.97)

    with (
        patch("app.ScryfallAPI.get_verified_price", return_value={"verified_price": 12.50, "price_key": "usd"}),
        patch("app.eBayAPI") as mock_ebay_cls,
    ):
        ebay_instance = Mock()
        ebay_instance.get_access_token.return_value = "token"
        ebay_instance.build_inventory_item_payload.return_value = {"product": {"title": "Path to Exile"}}
        ebay_instance.upsert_inventory_item.return_value = {"ok": True}
        ebay_instance.get_offer_by_sku.return_value = None
        ebay_instance.create_offer.return_value = "offer-123"
        ebay_instance.publish_offer.return_value = EbayListingState(
            sku="mtg-card-1",
            offer_id="offer-123",
            listing_id="listing-456",
            status="PUBLISHED",
            marketplace_id="EBAY_US",
        )
        mock_ebay_cls.return_value = ebay_instance

        # Step 1: Upload file to Google Drive + scan + import into frontend DB
        upload_response = client.post(
            "/api/integrations/google-drive/scan-import",
            data={
                "file": (BytesIO(b"image-content"), "path-to-exile.jpg"),
                "min_confidence": "0.95",
            },
            content_type="multipart/form-data",
        )

        assert upload_response.status_code == 200
        upload_payload = upload_response.get_json()
        assert upload_payload["success"] is True
        assert upload_payload["result"]["scanner"]["status"] == "success"
        assert upload_payload["result"]["scanner"]["confidence"] >= 0.95
        assert upload_payload["result"]["import_result"]["added"] == 1

        # Step 2: Verify card is visible through frontend API
        search_response = client.get("/api/cards/search?q=Path")
        assert search_response.status_code == 200
        cards = search_response.get_json()
        assert len(cards) == 1
        card_id = cards[0]["id"]
        assert cards[0]["name"] == "Path to Exile"

        # Step 3: Create eBay draft listing
        draft_response = client.post(
            "/api/ebay/listings",
            json={"card_id": card_id, "price": 12.50, "quantity": 1, "condition": "NM"},
        )
        assert draft_response.status_code == 200
        draft_payload = draft_response.get_json()
        assert draft_payload["success"] is True
        assert draft_payload["offer_id"] == "offer-123"

        # Step 4: Publish listing to eBay
        publish_response = client.post(f"/api/ebay/cards/{card_id}/publish")
        assert publish_response.status_code == 200
        publish_payload = publish_response.get_json()
        assert publish_payload["success"] is True
        assert publish_payload["listing_id"] == "listing-456"

        # Step 5: Validate DB has published listing
        db = session_factory()
        try:
            persisted_card = db.query(Card).filter(Card.id == card_id).first()
            assert persisted_card is not None
            assert persisted_card.ebay_offer_id == "offer-123"
            assert persisted_card.ebay_listing_id == "listing-456"
            assert persisted_card.list_on_ebay is True
        finally:
            db.close()


@patch("services.google_drive_pipeline.LangChainScannerClient")
@patch("services.google_drive_pipeline.GoogleDriveClient")
def test_drive_scan_rejects_low_confidence_result(
    mock_drive_cls,
    mock_scanner_cls,
    e2e_client_and_session,
):
    """Strict confidence gate must reject scans below threshold and avoid DB insert."""
    client, _ = e2e_client_and_session
    _mock_drive_and_scanner(mock_drive_cls, mock_scanner_cls, confidence=0.61)

    response = client.post(
        "/api/integrations/google-drive/scan-import",
        data={
            "file": (BytesIO(b"image-content"), "low-confidence.jpg"),
            "min_confidence": "0.90",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert "below required" in payload["error"]

    search_response = client.get("/api/cards/search?q=Path")
    assert search_response.status_code == 200
    assert search_response.get_json() == []
