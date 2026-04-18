"""eBay Inventory API client for trading card listings."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import requests

from config import Config


TRADING_CARD_CATEGORY_IDS = {"183050", "183454", "261328"}
DEFAULT_MARKETPLACE = "EBAY_US"
DEFAULT_CATEGORY_ID = "183454"
DEFAULT_CURRENCY = "USD"
DEFAULT_LANGUAGE = "en-US"


class EbayAPIError(RuntimeError):
    """Raised when the eBay API returns a user-actionable failure."""


@dataclass(frozen=True)
class EbayListingState:
    sku: str
    offer_id: str
    listing_id: Optional[str]
    status: str
    marketplace_id: str

    @property
    def listing_url(self) -> Optional[str]:
        if not self.listing_id:
            return None
        hostname = "sandbox.ebay.com" if Config.EBAY_SANDBOX_MODE else "www.ebay.com"
        return f"https://{hostname}/itm/{self.listing_id}"


class eBayAPI:
    """Client for eBay's Inventory + Account + Metadata APIs."""

    def __init__(self):
        self.base_url = "https://api.sandbox.ebay.com" if Config.EBAY_SANDBOX_MODE else "https://api.ebay.com"
        self.marketplace_id = Config.EBAY_MARKETPLACE_ID or DEFAULT_MARKETPLACE
        self.category_id = str(Config.EBAY_CATEGORY_ID or DEFAULT_CATEGORY_ID)
        self.currency = Config.EBAY_CURRENCY or DEFAULT_CURRENCY
        self.content_language = Config.EBAY_CONTENT_LANGUAGE or DEFAULT_LANGUAGE

        self.app_id = Config.EBAY_APP_ID
        self.dev_id = Config.EBAY_DEV_ID
        self.user_token = Config.EBAY_USER_TOKEN
        self.client_id = Config.EBAY_CLIENT_ID
        self.client_secret = Config.EBAY_CLIENT_SECRET
        self.refresh_token = Config.EBAY_REFRESH_TOKEN

        self._access_token: Optional[str] = None
        self._auth_mode: Optional[str] = None
        self._last_auth_status: Optional[int] = None
        self._policy_cache: Optional[dict[str, str]] = None
        self._location_cache: Optional[str] = None
        self._condition_policy_cache: dict[str, dict[str, Any]] = {}

    def _headers(self, *, include_json: bool = True, include_language: bool = False) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._access_token}"}
        if include_json:
            headers["Content-Type"] = "application/json"
        if include_language:
            headers["Content-Language"] = self.content_language
        return headers

    def _parse_error(self, response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"eBay API error {response.status_code}"

        messages: list[str] = []
        for bucket in ("errors", "warnings"):
            for entry in payload.get(bucket, []):
                message = entry.get("longMessage") or entry.get("message")
                if message:
                    messages.append(message)
        if messages:
            return "; ".join(messages)
        if isinstance(payload, dict):
            return json.dumps(payload)
        return f"eBay API error {response.status_code}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        expected_statuses: Iterable[int] = (200,),
        include_language: bool = False,
    ) -> requests.Response:
        if not self._access_token and not self.get_access_token():
            raise EbayAPIError("Unable to authenticate with eBay.")

        response = requests.request(
            method,
            f"{self.base_url}{path}",
            headers=self._headers(include_language=include_language),
            params=params,
            json=payload,
            timeout=20,
        )
        if response.status_code not in set(expected_statuses):
            raise EbayAPIError(self._parse_error(response))
        return response

    def get_access_token(self) -> Optional[str]:
        """Resolve a usable sell token."""
        if self._access_token:
            return self._access_token

        if self.user_token:
            self._access_token = self.user_token
            self._auth_mode = "user_token"
            return self._access_token

        if not all([self.client_id, self.client_secret, self.refresh_token]):
            return None

        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        response = requests.post(
            f"{self.base_url}/identity/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "scope": "https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.account",
            },
            timeout=20,
        )
        if response.status_code != 200:
            return None

        try:
            result = response.json()
        except ValueError:
            return None

        self._access_token = result.get("access_token")
        self._auth_mode = "oauth_refresh"
        return self._access_token

    def validate_rest_access(self) -> bool:
        """Check whether the current credentials can talk to Sell APIs."""
        if not self._access_token and not self.get_access_token():
            self._last_auth_status = None
            return False

        try:
            response = requests.get(
                f"{self.base_url}/sell/account/v1/privilege",
                headers=self._headers(include_json=False),
                timeout=20,
            )
            self._last_auth_status = response.status_code
            return response.status_code == 200
        except requests.exceptions.RequestException:
            self._last_auth_status = None
            return False

    def resolve_location_key(self) -> str:
        if self._location_cache:
            return self._location_cache

        if Config.EBAY_MERCHANT_LOCATION_KEY:
            self._location_cache = Config.EBAY_MERCHANT_LOCATION_KEY
            return self._location_cache

        try:
            response = self._request("GET", "/sell/inventory/v1/location", expected_statuses=(200,))
        except EbayAPIError as exc:
            raise EbayAPIError(
                "Unable to discover an eBay inventory location for this sandbox account. "
                "Set EBAY_MERCHANT_LOCATION_KEY or configure a seller location in sandbox."
            ) from exc
        locations = (response.json() or {}).get("locations", [])
        enabled = next(
            (
                item.get("merchantLocationKey")
                for item in locations
                if item.get("merchantLocationStatus", "ENABLED") == "ENABLED" and item.get("merchantLocationKey")
            ),
            None,
        )
        if not enabled:
            raise EbayAPIError(
                "No enabled eBay inventory location found. Set EBAY_MERCHANT_LOCATION_KEY or create a sandbox location first."
            )
        self._location_cache = enabled
        return enabled

    def resolve_listing_policies(self) -> dict[str, str]:
        if self._policy_cache:
            return self._policy_cache

        policy_ids = {
            "paymentPolicyId": Config.EBAY_PAYMENT_POLICY_ID,
            "fulfillmentPolicyId": Config.EBAY_FULFILLMENT_POLICY_ID,
            "returnPolicyId": Config.EBAY_RETURN_POLICY_ID,
        }
        if all(policy_ids.values()):
            self._policy_cache = policy_ids
            return policy_ids

        endpoints = {
            "paymentPolicyId": ("/sell/account/v1/payment_policy", "paymentPolicies", "paymentPolicyId"),
            "fulfillmentPolicyId": (
                "/sell/account/v1/fulfillment_policy",
                "fulfillmentPolicies",
                "fulfillmentPolicyId",
            ),
            "returnPolicyId": ("/sell/account/v1/return_policy", "returnPolicies", "returnPolicyId"),
        }

        for config_key, (path, collection_key, id_key) in endpoints.items():
            if policy_ids.get(config_key):
                continue
            try:
                response = self._request(
                    "GET",
                    path,
                    params={"marketplace_id": self.marketplace_id},
                    expected_statuses=(200,),
                )
            except EbayAPIError as exc:
                raise EbayAPIError(
                    "This sandbox account is not eligible for eBay business policies. "
                    "Configure policy IDs explicitly or switch to an inventory-enabled sandbox seller account."
                ) from exc
            collection = (response.json() or {}).get(collection_key) or []
            policy_ids[config_key] = next((item.get(id_key) for item in collection if item.get(id_key)), None)

        if not all(policy_ids.values()):
            raise EbayAPIError(
                "Missing eBay business policies. Configure payment, fulfillment, and return policies in sandbox or provide their IDs in the environment."
            )

        self._policy_cache = policy_ids
        return policy_ids

    def get_condition_policy(self, category_id: str) -> dict[str, Any]:
        if category_id in self._condition_policy_cache:
            return self._condition_policy_cache[category_id]

        response = self._request(
            "GET",
            f"/sell/metadata/v1/marketplace/{self.marketplace_id}/get_item_condition_policies",
            params={"filter": f"categoryIds:{{{category_id}}}"},
            expected_statuses=(200,),
        )
        policy = next(iter((response.json() or {}).get("itemConditionPolicies") or []), None)
        if not policy:
            raise EbayAPIError(f"Unable to load condition metadata for category {category_id}.")
        self._condition_policy_cache[category_id] = policy
        return policy

    def build_card_condition(self, *, category_id: str, card_condition: Optional[str]) -> dict[str, Any]:
        normalized = (card_condition or "").strip().lower()
        if category_id not in TRADING_CARD_CATEGORY_IDS:
            return {"condition": "USED_VERY_GOOD" if normalized else "NEW"}

        policy = self.get_condition_policy(category_id)
        ungraded = next(
            (item for item in policy.get("itemConditions", []) if str(item.get("conditionId")) == "4000"),
            None,
        )
        if not ungraded:
            raise EbayAPIError("eBay condition metadata for trading cards is missing the Ungraded condition.")

        descriptor = next(
            (
                item
                for item in ungraded.get("conditionDescriptors", [])
                if item.get("conditionDescriptorName", "").lower() == "card condition"
            ),
            None,
        )
        if not descriptor:
            return {"condition": "USED_VERY_GOOD"}

        mapping = {
            "near mint": "near mint or better",
            "nm": "near mint or better",
            "mint": "near mint or better",
            "excellent": "excellent",
            "lightly played": "excellent",
            "lp": "excellent",
            "very good": "very good",
            "moderately played": "very good",
            "mp": "very good",
            "good": "very good",
            "poor": "poor",
            "heavily played": "poor",
            "hp": "poor",
            "damaged": "poor",
        }
        target_name = mapping.get(normalized, "near mint or better")
        descriptor_value = next(
            (
                item
                for item in descriptor.get("conditionDescriptorValues", [])
                if item.get("conditionDescriptorValueName", "").lower() == target_name
            ),
            None,
        )
        if not descriptor_value:
            raise EbayAPIError(f"Unable to map card condition '{card_condition}' to an eBay descriptor.")

        return {
            "condition": "USED_VERY_GOOD",
            "conditionDescriptors": [
                {
                    "name": str(descriptor.get("conditionDescriptorId")),
                    "values": [str(descriptor_value.get("conditionDescriptorValueId"))],
                }
            ],
        }

    def build_inventory_item_payload(
        self,
        *,
        card: Any,
        quantity: int,
        description: str,
        card_condition: Optional[str],
        image_url: Optional[str] = None,
    ) -> dict[str, Any]:
        condition_payload = self.build_card_condition(category_id=self.category_id, card_condition=card_condition)
        aspects = {
            "Game": ["Magic: The Gathering"],
            "Card Name": [card.name],
            "Manufacturer": ["Wizards of the Coast"],
        }
        if getattr(card, "set_name", None):
            aspects["Set"] = [card.set_name]
        elif getattr(card, "set_code", None):
            aspects["Set"] = [card.set_code]
        if getattr(card, "collector_number", None):
            aspects["Card Number"] = [str(card.collector_number)]

        payload: dict[str, Any] = {
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": int(quantity),
                }
            },
            "condition": condition_payload["condition"],
            "product": {
                "title": card.name[:80],
                "description": description,
                "aspects": aspects,
            },
        }
        if condition_payload.get("conditionDescriptors"):
            payload["conditionDescriptors"] = condition_payload["conditionDescriptors"]
        if image_url:
            payload["product"]["imageUrls"] = [image_url]
        return payload

    def upsert_inventory_item(self, *, sku: str, payload: dict[str, Any]) -> None:
        self._request(
            "PUT",
            f"/sell/inventory/v1/inventory_item/{sku}",
            payload=payload,
            expected_statuses=(200, 201, 204),
            include_language=True,
        )

    def create_offer(
        self,
        *,
        sku: str,
        price: float,
        quantity: int,
        description: str,
    ) -> str:
        policies = self.resolve_listing_policies()
        location_key = self.resolve_location_key()
        payload = {
            "sku": sku,
            "marketplaceId": self.marketplace_id,
            "format": "FIXED_PRICE",
            "availableQuantity": int(quantity),
            "categoryId": self.category_id,
            "merchantLocationKey": location_key,
            "listingDescription": description,
            "listingPolicies": policies,
            "pricingSummary": {
                "price": {
                    "value": f"{float(price):.2f}",
                    "currency": self.currency,
                }
            },
        }
        response = self._request(
            "POST",
            "/sell/inventory/v1/offer",
            payload=payload,
            expected_statuses=(200, 201),
            include_language=True,
        )
        offer_id = (response.json() or {}).get("offerId")
        if not offer_id:
            raise EbayAPIError("eBay created the offer but did not return an offerId.")
        return offer_id

    def get_offer(self, offer_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/sell/inventory/v1/offer/{offer_id}", expected_statuses=(200,))
        return response.json() or {}

    def get_offer_by_sku(self, sku: str) -> Optional[dict[str, Any]]:
        if not self._access_token and not self.get_access_token():
            raise EbayAPIError("Unable to authenticate with eBay.")

        response = requests.get(
            f"{self.base_url}/sell/inventory/v1/offer",
            headers=self._headers(),
            params={"sku": sku, "marketplace_id": self.marketplace_id},
            timeout=20,
        )
        if response.status_code == 200:
            offers = (response.json() or {}).get("offers") or []
            return offers[0] if offers else None

        message = self._parse_error(response)
        if response.status_code in (204, 404) or "offer is not available" in message.lower():
            return None
        raise EbayAPIError(message)

    def update_offer(
        self,
        *,
        offer_id: str,
        price: float,
        quantity: int,
        description: Optional[str] = None,
    ) -> dict[str, Any]:
        existing = self.get_offer(offer_id)
        existing["availableQuantity"] = int(quantity)
        existing.setdefault("pricingSummary", {})
        existing["pricingSummary"]["price"] = {
            "value": f"{float(price):.2f}",
            "currency": self.currency,
        }
        if description:
            existing["listingDescription"] = description

        self._request(
            "PUT",
            f"/sell/inventory/v1/offer/{offer_id}",
            payload=existing,
            expected_statuses=(200, 204),
            include_language=True,
        )
        return self.get_offer(offer_id)

    def publish_offer(self, offer_id: str) -> EbayListingState:
        response = self._request(
            "POST",
            f"/sell/inventory/v1/offer/{offer_id}/publish",
            expected_statuses=(200,),
        )
        payload = response.json() or {}
        return EbayListingState(
            sku=payload.get("sku") or "",
            offer_id=payload.get("offerId") or offer_id,
            listing_id=payload.get("listingId"),
            status="PUBLISHED",
            marketplace_id=self.marketplace_id,
        )

    def bulk_publish_offers(self, offer_ids: list[str]) -> list[EbayListingState]:
        response = self._request(
            "POST",
            "/sell/inventory/v1/bulk_publish_offer",
            payload={"requests": [{"offerId": offer_id} for offer_id in offer_ids]},
            expected_statuses=(200,),
        )
        states: list[EbayListingState] = []
        for item in (response.json() or {}).get("responses", []):
            if int(item.get("statusCode", 0)) != 200:
                message = "; ".join(error.get("message", "") for error in item.get("errors", []))
                raise EbayAPIError(message or f"Bulk publish failed for offer {item.get('offerId')}.")
            states.append(
                EbayListingState(
                    sku=item.get("sku") or "",
                    offer_id=item.get("offerId") or "",
                    listing_id=item.get("listingId"),
                    status="PUBLISHED",
                    marketplace_id=self.marketplace_id,
                )
            )
        return states
