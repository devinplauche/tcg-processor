import time
import uuid

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app as app_module
from database import Base
from models import Card
from services.ebay_api import EbayAPIError, eBayAPI


def _has_ebay_env() -> bool:
    from config import Config

    return bool(
        Config.EBAY_APP_ID
        and Config.EBAY_DEV_ID
        and (Config.EBAY_USER_TOKEN or (Config.EBAY_CLIENT_ID and Config.EBAY_CLIENT_SECRET and Config.EBAY_REFRESH_TOKEN))
    )


@pytest.fixture
def live_ebay_client(tmp_path, monkeypatch):
    db_path = tmp_path / "ebay-live.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(app_module, "SessionLocal", TestingSessionLocal)
    app_module.app.config["TESTING"] = True

    yield app_module.app.test_client(), TestingSessionLocal

    Base.metadata.drop_all(bind=engine)


def _seed_live_card(session, *, name: str, scryfall_id: str, set_code: str, collector_number: str):
    card = Card(
        scryfall_id=scryfall_id,
        name=name,
        set_code=set_code,
        set_name=set_code,
        collector_number=collector_number,
        foil=False,
        rarity="rare",
        quantity=1,
        condition="Near Mint",
        language="en",
        purchase_price=1.0,
    )
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def _assert_sandbox_page(listing_url: str):
    for _ in range(5):
        response = requests.get(listing_url, timeout=20, allow_redirects=True)
        if response.status_code < 500:
            assert response.status_code in (200, 301, 302)
            return
        time.sleep(2)
    pytest.fail(f"Sandbox listing page never became reachable: {listing_url}")


@pytest.mark.integration
def test_live_ebay_create_update_and_bulk_publish_are_visible(live_ebay_client):
    if not _has_ebay_env():
        pytest.skip("eBay credentials not configured for live sandbox listing test")

    api = eBayAPI()
    if not api.get_access_token():
        pytest.skip("eBay credentials are configured but no access token could be resolved")
    try:
        api.resolve_listing_policies()
        api.resolve_location_key()
    except EbayAPIError as exc:
        pytest.skip(f"Sandbox account is not ready for Inventory API listing flow: {exc}")

    client, SessionLocal = live_ebay_client
    db = SessionLocal()

    card_one = _seed_live_card(
        db,
        name=f"Codex Sandbox Test {uuid.uuid4().hex[:8]}",
        scryfall_id="4e2fe951-4820-4555-8cee-621c66ed8620",
        set_code="SLD",
        collector_number="226",
    )
    card_two = _seed_live_card(
        db,
        name=f"Codex Bulk Publish {uuid.uuid4().hex[:8]}",
        scryfall_id="c8d672ba-83bd-4bf0-b8f4-5eb382f16a62",
        set_code="LEA",
        collector_number="244",
    )
    card_one_id = card_one.id
    card_two_id = card_two.id
    db.close()

    create_response = client.post("/api/ebay/listings", json={"card_id": card_one_id})
    create_payload = create_response.get_json()
    assert create_response.status_code == 200, create_payload
    assert create_payload["success"] is True
    assert create_payload["offer_id"]

    update_response = client.patch(
        f"/api/ebay/cards/{card_one_id}/listing",
        json={"price": 6.25, "quantity": 1},
    )
    update_payload = update_response.get_json()
    assert update_response.status_code == 200, update_payload
    assert update_payload["success"] is True
    assert update_payload["price_used"] == 6.25

    publish_response = client.post(f"/api/ebay/cards/{card_one_id}/publish")
    publish_payload = publish_response.get_json()
    assert publish_response.status_code == 200, publish_payload
    assert publish_payload["success"] is True
    assert publish_payload["listing_id"]
    assert publish_payload["listing_url"]
    _assert_sandbox_page(publish_payload["listing_url"])

    second_create = client.post("/api/ebay/listings", json={"card_id": card_two_id})
    second_payload = second_create.get_json()
    assert second_create.status_code == 200, second_payload
    assert second_payload["success"] is True

    bulk_response = client.post("/api/ebay/listings/bulk-publish", json={"card_ids": [card_two_id]})
    bulk_payload = bulk_response.get_json()
    assert bulk_response.status_code == 200, bulk_payload
    assert bulk_payload["success"] is True
    assert bulk_payload["results"][0]["listing_id"]
    assert bulk_payload["results"][0]["listing_url"]
    _assert_sandbox_page(bulk_payload["results"][0]["listing_url"])
