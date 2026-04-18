"""Scryfall client and pricing helpers."""

from __future__ import annotations

import json
from typing import Dict, List, Optional

import requests

from services.ebay_api import EbayAPIError, eBayAPI


class ScryfallAPI:
    """Scryfall API client for MTG card data."""

    BASE_URL = "https://api.scryfall.com"

    @staticmethod
    def get_card_by_id(scryfall_id: str) -> Optional[Dict]:
        """Fetch card details from Scryfall by ID."""
        try:
            response = requests.get(f"{ScryfallAPI.BASE_URL}/cards/{scryfall_id}", timeout=10)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def search_cards(query: str, limit: int = 10) -> List[Dict]:
        """Search for cards by query string."""
        try:
            response = requests.get(
                f"{ScryfallAPI.BASE_URL}/cards/search",
                params={"q": query, "unique": "cards"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])[:limit]
        except (requests.exceptions.RequestException, ValueError, json.JSONDecodeError):
            return []

    @staticmethod
    def get_verified_price(scryfall_id: str, *, foil: bool = False) -> Optional[Dict[str, Optional[float]]]:
        """Fetch the latest Scryfall USD price snapshot for a card."""
        card = ScryfallAPI.get_card_by_id(scryfall_id)
        if not card:
            return None

        prices = card.get("prices") or {}
        preferred_key = "usd_foil" if foil else "usd"
        fallback_key = "usd" if foil else "usd_foil"

        raw_price = prices.get(preferred_key) or prices.get(fallback_key)
        try:
            verified_price = float(raw_price) if raw_price is not None else None
        except (TypeError, ValueError):
            verified_price = None

        return {
            "verified_price": verified_price,
            "price_key": preferred_key if prices.get(preferred_key) else fallback_key,
            "card_name": card.get("name"),
            "image_url": (card.get("image_uris") or {}).get("normal"),
        }


# Backward-compatible re-export while callers migrate to services.ebay_api.
