import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app as app_module
from database import Base
from models import Card
from services.ebay_api import EbayAPIError, EbayListingState


@pytest.fixture
def ebay_test_client(tmp_path, monkeypatch):
    db_path = tmp_path / "ebay-flow.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(app_module, "SessionLocal", TestingSessionLocal)
    app_module.app.config["TESTING"] = True

    yield app_module.app.test_client(), TestingSessionLocal

    Base.metadata.drop_all(bind=engine)


def _create_card(session, **overrides):
    card = Card(
        scryfall_id=overrides.get("scryfall_id", str(uuid.uuid4())),
        name=overrides.get("name", "Path to Exile"),
        set_code=overrides.get("set_code", "SLD"),
        set_name=overrides.get("set_name", "Secret Lair Drop"),
        collector_number=overrides.get("collector_number", "226"),
        foil=overrides.get("foil", False),
        rarity=overrides.get("rarity", "rare"),
        quantity=overrides.get("quantity", 1),
        condition=overrides.get("condition", "Near Mint"),
        language=overrides.get("language", "en"),
        purchase_price=overrides.get("purchase_price", 2.5),
    )
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def test_create_listing_uses_verified_scryfall_price_and_persists_offer(ebay_test_client, monkeypatch):
    client, SessionLocal = ebay_test_client
    db = SessionLocal()
    card = _create_card(db, purchase_price=0.0)
    db.close()

    api = SimpleNamespace(
        get_access_token=lambda: "token",
        build_inventory_item_payload=lambda **kwargs: {"sku": f"mtg-card-{card.id}", **kwargs},
        upsert_inventory_item=lambda **kwargs: None,
        get_offer_by_sku=lambda sku: None,
        create_offer=lambda **kwargs: "offer-123",
    )

    monkeypatch.setattr(app_module, "eBayAPI", lambda: api)
    monkeypatch.setattr(
        app_module.ScryfallAPI,
        "get_verified_price",
        staticmethod(lambda *args, **kwargs: {"verified_price": 4.25, "price_key": "usd", "image_url": "https://img"}),
    )

    response = client.post("/api/ebay/listings", json={"card_id": card.id})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["offer_id"] == "offer-123"
    assert payload["price_used"] == 4.25
    assert payload["listing_id"] is None

    db = SessionLocal()
    stored = db.query(Card).filter(Card.id == card.id).first()
    assert stored.ebay_offer_id == "offer-123"
    assert stored.ebay_listing_id is None
    db.close()


def test_update_listing_updates_existing_offer(ebay_test_client, monkeypatch):
    client, SessionLocal = ebay_test_client
    db = SessionLocal()
    card = _create_card(db, purchase_price=1.0)
    card.ebay_offer_id = "offer-456"
    db.commit()
    card_id = card.id
    db.close()

    api = SimpleNamespace(
        get_access_token=lambda: "token",
        build_inventory_item_payload=lambda **kwargs: {"ok": True},
        upsert_inventory_item=lambda **kwargs: None,
        update_offer=lambda **kwargs: {"offerId": kwargs["offer_id"], "availableQuantity": kwargs["quantity"]},
    )

    monkeypatch.setattr(app_module, "eBayAPI", lambda: api)
    monkeypatch.setattr(
        app_module.ScryfallAPI,
        "get_verified_price",
        staticmethod(lambda *args, **kwargs: {"verified_price": 7.5, "price_key": "usd", "image_url": None}),
    )

    response = client.patch(f"/api/ebay/cards/{card_id}/listing", json={"price": 8.0, "quantity": 3})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["card_id"] == card_id
    assert payload["offer_id"] == "offer-456"
    assert payload["price_used"] == 8.0
    assert payload["result"]["availableQuantity"] == 3


def test_bulk_publish_persists_listing_ids(ebay_test_client, monkeypatch):
    client, SessionLocal = ebay_test_client
    db = SessionLocal()
    card_one = _create_card(db, name="Card One")
    card_two = _create_card(db, name="Card Two")
    card_one.ebay_offer_id = "offer-1"
    card_two.ebay_offer_id = "offer-2"
    db.commit()
    card_one_id = card_one.id
    card_two_id = card_two.id
    db.close()

    api = SimpleNamespace(
        get_access_token=lambda: "token",
        bulk_publish_offers=lambda offer_ids: [
                EbayListingState(
                    sku=f"mtg-card-{card_one_id}",
                    offer_id="offer-1",
                    listing_id="listing-1",
                    status="PUBLISHED",
                    marketplace_id="EBAY_US",
                ),
                EbayListingState(
                    sku=f"mtg-card-{card_two_id}",
                    offer_id="offer-2",
                    listing_id="listing-2",
                    status="PUBLISHED",
                    marketplace_id="EBAY_US",
                ),
        ],
    )

    monkeypatch.setattr(app_module, "eBayAPI", lambda: api)

    response = client.post("/api/ebay/listings/bulk-publish", json={"card_ids": [card_one_id, card_two_id]})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["published_count"] == 2
    assert {item["listing_id"] for item in payload["results"]} == {"listing-1", "listing-2"}

    db = SessionLocal()
    refreshed = db.query(Card).filter(Card.id.in_([card_one_id, card_two_id])).all()
    assert {card.ebay_listing_id for card in refreshed} == {"listing-1", "listing-2"}
    db.close()


def test_publish_returns_diagnostics_on_publish_failure(ebay_test_client, monkeypatch):
    client, SessionLocal = ebay_test_client
    db = SessionLocal()
    card = _create_card(db, name="Card Publish Failure")
    card.ebay_offer_id = "offer-failing"
    db.commit()
    card_id = card.id
    db.close()

    api = SimpleNamespace(
        get_access_token=lambda: "token",
        publish_offer=lambda offer_id: (_ for _ in ()).throw(EbayAPIError("system error")),
        diagnose_publish_offer=lambda offer_id: {
            "offer_id": offer_id,
            "summary": {
                "all_prereq_reads_ok": True,
                "likely_sandbox_mutation_issue": True,
            },
            "checks": {
                "offer": {"ok": True, "status": 200},
            },
        },
    )

    monkeypatch.setattr(app_module, "eBayAPI", lambda: api)

    response = client.post(f"/api/ebay/cards/{card_id}/publish")
    payload = response.get_json()

    assert response.status_code == 502
    assert payload["success"] is False
    assert "system error" in payload["error"].lower()
    assert payload["diagnostics"]["offer_id"] == "offer-failing"
    assert payload["diagnostics"]["summary"]["likely_sandbox_mutation_issue"] is True
