"""eBay Inventory API client for trading card listings."""

from __future__ import annotations

import base64
import json
import os
import time
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

    @staticmethod
    def _correlation_ids(response: requests.Response) -> dict[str, str | None]:
        return {
            "x_ebay_c_request_id": response.headers.get("x-ebay-c-request-id"),
            "rlogid": response.headers.get("rlogid"),
        }

    def _raw_request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        include_language: bool = False,
    ) -> requests.Response:
        if not self._access_token and not self.get_access_token():
            raise EbayAPIError("Unable to authenticate with eBay.")

        return requests.request(
            method,
            f"{self.base_url}{path}",
            headers=self._headers(include_language=include_language),
            params=params,
            json=payload,
            timeout=20,
        )

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
        response = self._raw_request(
            method,
            path,
            params=params,
            payload=payload,
            include_language=include_language,
        )
        if response.status_code not in set(expected_statuses):
            message = self._parse_error(response)
            if response.status_code >= 500:
                corr = self._correlation_ids(response)
                message = (
                    f"{message} (status={response.status_code}, "
                    f"x-ebay-c-request-id={corr['x_ebay_c_request_id']}, rlogid={corr['rlogid']})"
                )
            raise EbayAPIError(message)
        return response

    def _probe_endpoint(
        self,
        *,
        key: str,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            response = self._raw_request(method, path, params=params)
            return {
                "name": key,
                "ok": 200 <= response.status_code < 300,
                "status": response.status_code,
                "path": path,
                "correlation": self._correlation_ids(response),
            }
        except Exception as exc:
            return {
                "name": key,
                "ok": False,
                "status": None,
                "path": path,
                "error": str(exc),
            }

    def diagnose_publish_offer(self, offer_id: str) -> dict[str, Any]:
        """Collect publish prerequisites and API signal for sandbox 502 debugging."""
        report: dict[str, Any] = {
            "offer_id": offer_id,
            "marketplace_id": self.marketplace_id,
            "base_url": self.base_url,
            "checks": {},
            "summary": {},
        }

        offer_path = f"/sell/inventory/v1/offer/{offer_id}"
        offer_response = self._raw_request("GET", offer_path)
        report["checks"]["offer"] = {
            "ok": offer_response.status_code == 200,
            "status": offer_response.status_code,
            "path": offer_path,
            "correlation": self._correlation_ids(offer_response),
        }

        if offer_response.status_code != 200:
            report["summary"] = {
                "all_prereq_reads_ok": False,
                "likely_sandbox_mutation_issue": False,
                "note": "Offer read failed; publish prerequisites cannot be verified.",
            }
            return report

        offer_payload = offer_response.json() or {}
        sku = offer_payload.get("sku")
        merchant_location_key = offer_payload.get("merchantLocationKey")
        listing_policies = offer_payload.get("listingPolicies") or {}

        report["summary"]["offer_snapshot"] = {
            "sku": sku,
            "merchantLocationKey": merchant_location_key,
            "paymentPolicyId": listing_policies.get("paymentPolicyId"),
            "fulfillmentPolicyId": listing_policies.get("fulfillmentPolicyId"),
            "returnPolicyId": listing_policies.get("returnPolicyId"),
        }

        if sku:
            report["checks"]["inventory_item"] = self._probe_endpoint(
                key="inventory_item",
                method="GET",
                path=f"/sell/inventory/v1/inventory_item/{sku}",
            )

        if merchant_location_key:
            report["checks"]["location"] = self._probe_endpoint(
                key="location",
                method="GET",
                path=f"/sell/inventory/v1/location/{merchant_location_key}",
            )

        policy_paths = {
            "payment_policy": ("/sell/account/v1/payment_policy", listing_policies.get("paymentPolicyId")),
            "fulfillment_policy": (
                "/sell/account/v1/fulfillment_policy",
                listing_policies.get("fulfillmentPolicyId"),
            ),
            "return_policy": ("/sell/account/v1/return_policy", listing_policies.get("returnPolicyId")),
        }
        for key, (base_path, policy_id) in policy_paths.items():
            if policy_id:
                report["checks"][key] = self._probe_endpoint(
                    key=key,
                    method="GET",
                    path=f"{base_path}/{policy_id}",
                )
            else:
                report["checks"][key] = {
                    "name": key,
                    "ok": False,
                    "status": None,
                    "path": base_path,
                    "error": "Missing policy id on offer",
                }

        check_values = [entry.get("ok", False) for entry in report["checks"].values()]
        all_reads_ok = bool(check_values) and all(check_values)
        report["summary"].update(
            {
                "all_prereq_reads_ok": all_reads_ok,
                "likely_sandbox_mutation_issue": bool(Config.EBAY_SANDBOX_MODE and all_reads_ok),
                "next_action": (
                    "Collect x-ebay-c-request-id and rlogid from failing publish responses and open an eBay developer support ticket."
                    if Config.EBAY_SANDBOX_MODE and all_reads_ok
                    else "Fix failing prerequisite checks before retrying publish."
                ),
            }
        )
        return report

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

    def check_seller_registration(self) -> dict[str, Any]:
        """Return privilege info including whether seller registration is complete."""
        if not self._access_token and not self.get_access_token():
            return {"ok": False, "sellerRegistrationCompleted": False, "error": "no_token"}
        try:
            response = requests.get(
                f"{self.base_url}/sell/account/v1/privilege",
                headers=self._headers(include_json=False),
                timeout=20,
            )
            if response.status_code != 200:
                return {"ok": False, "sellerRegistrationCompleted": False, "status": response.status_code}
            data = response.json() or {}
            registered = bool(data.get("sellerRegistrationCompleted", False))
            return {"ok": True, "sellerRegistrationCompleted": registered, **data}
        except requests.exceptions.RequestException as exc:
            return {"ok": False, "sellerRegistrationCompleted": False, "error": str(exc)}

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

    def list_locations(self) -> list[dict[str, Any]]:
        response = self._request("GET", "/sell/inventory/v1/location", expected_statuses=(200,))
        return (response.json() or {}).get("locations", []) or []

    def create_location(self, *, merchant_location_key: str, payload: dict[str, Any]) -> None:
        self._request(
            "POST",
            f"/sell/inventory/v1/location/{merchant_location_key}",
            payload=payload,
            expected_statuses=(200, 201, 204),
            include_language=True,
        )

    def _bootstrap_location_payload(self) -> dict[str, Any]:
        street_1 = os.getenv("EBAY_LOCATION_STREET1", "123 Main St")
        city = os.getenv("EBAY_LOCATION_CITY", "San Jose")
        state = os.getenv("EBAY_LOCATION_STATE", "CA")
        postal = os.getenv("EBAY_LOCATION_POSTAL_CODE", "95125")
        country = os.getenv("EBAY_LOCATION_COUNTRY", "US")
        phone = os.getenv("EBAY_LOCATION_PHONE", "4081234567")
        name = os.getenv("EBAY_LOCATION_NAME", "Default Inventory Location")

        return {
            "name": name,
            "merchantLocationStatus": "ENABLED",
            "location": {
                "address": {
                    "addressLine1": street_1,
                    "city": city,
                    "stateOrProvince": state,
                    "postalCode": postal,
                    "country": country,
                }
            },
            "locationTypes": ["WAREHOUSE"],
            "phone": phone,
        }

    def ensure_location_key(self) -> str:
        """Resolve a usable inventory location, optionally creating one from env defaults."""
        try:
            return self.resolve_location_key()
        except EbayAPIError:
            auto_create = os.getenv("EBAY_AUTO_CREATE_LOCATION", "false").lower() in ("1", "true", "yes", "t")
            if not auto_create:
                raise

            merchant_location_key = os.getenv("EBAY_MERCHANT_LOCATION_KEY", "mtg-inventory-default")
            payload = self._bootstrap_location_payload()
            self.create_location(merchant_location_key=merchant_location_key, payload=payload)

            self._location_cache = None
            return self.resolve_location_key()

    def list_policy_ids(self) -> dict[str, list[str]]:
        endpoints = {
            "paymentPolicyId": ("/sell/account/v1/payment_policy", "paymentPolicies", "paymentPolicyId"),
            "fulfillmentPolicyId": (
                "/sell/account/v1/fulfillment_policy",
                "fulfillmentPolicies",
                "fulfillmentPolicyId",
            ),
            "returnPolicyId": ("/sell/account/v1/return_policy", "returnPolicies", "returnPolicyId"),
        }
        output: dict[str, list[str]] = {
            "paymentPolicyId": [],
            "fulfillmentPolicyId": [],
            "returnPolicyId": [],
        }
        for key, (path, collection_key, id_key) in endpoints.items():
            response = self._request(
                "GET",
                path,
                params={"marketplace_id": self.marketplace_id},
                expected_statuses=(200,),
            )
            collection = (response.json() or {}).get(collection_key) or []
            output[key] = [str(item.get(id_key)) for item in collection if item.get(id_key)]
        return output

    def _business_policy_category_type(self) -> str:
        return os.getenv("EBAY_POLICY_CATEGORY_TYPE", "ALL_EXCLUDING_MOTORS_VEHICLES")

    def create_default_payment_policy(self) -> dict[str, Any]:
        base_payload = {
            "name": os.getenv("EBAY_PAYMENT_POLICY_NAME", "MTG Payment Policy"),
            "description": "Auto-created payment policy for MTG inventory",
            "marketplaceId": self.marketplace_id,
            "categoryTypes": [{"name": self._business_policy_category_type()}],
            "immediatePay": False,
        }
        variants = [
            {**base_payload, "paymentMethods": [{"paymentMethodType": "PAYPAL"}]},
            {**base_payload, "paymentMethods": [{"paymentMethodType": "CREDIT_CARD"}]},
            base_payload,
        ]

        last_error: Optional[Exception] = None
        for payload in variants:
            try:
                response = self._request(
                    "POST",
                    "/sell/account/v1/payment_policy",
                    payload=payload,
                    expected_statuses=(200, 201),
                    include_language=True,
                )
                return response.json() or {}
            except Exception as exc:
                last_error = exc

        if last_error:
            raise last_error
        raise EbayAPIError("Unable to create payment policy")

    def create_default_fulfillment_policy(self) -> dict[str, Any]:
        payload = {
            "name": os.getenv("EBAY_FULFILLMENT_POLICY_NAME", "MTG Fulfillment Policy"),
            "description": "Auto-created fulfillment policy for MTG inventory",
            "marketplaceId": self.marketplace_id,
            "categoryTypes": [{"name": self._business_policy_category_type()}],
            "handlingTime": {"unit": "DAY", "value": int(os.getenv("EBAY_POLICY_HANDLING_DAYS", "3"))},
            "shippingOptions": [
                {
                    "optionType": "DOMESTIC",
                    "costType": "FLAT_RATE",
                    "shippingServices": [
                        {
                            "shippingCarrierCode": os.getenv("EBAY_POLICY_SHIPPING_CARRIER", "USPS"),
                            "shippingServiceCode": os.getenv("EBAY_POLICY_SHIPPING_SERVICE", "USPSFirstClass"),
                            "shippingCost": {"currency": self.currency, "value": os.getenv("EBAY_POLICY_SHIPPING_COST", "0.00")},
                        }
                    ],
                }
            ],
        }
        response = self._request(
            "POST",
            "/sell/account/v1/fulfillment_policy",
            payload=payload,
            expected_statuses=(200, 201),
            include_language=True,
        )
        return response.json() or {}

    def create_default_return_policy(self) -> dict[str, Any]:
        days = int(os.getenv("EBAY_POLICY_RETURN_DAYS", "30"))
        payload = {
            "name": os.getenv("EBAY_RETURN_POLICY_NAME", "MTG Return Policy"),
            "description": "Auto-created return policy for MTG inventory",
            "marketplaceId": self.marketplace_id,
            "categoryTypes": [{"name": self._business_policy_category_type()}],
            "returnsAccepted": True,
            "returnPeriod": {"value": days, "unit": "DAY"},
            "refundMethod": "MONEY_BACK",
            "returnShippingCostPayer": os.getenv("EBAY_POLICY_RETURN_PAYER", "BUYER"),
        }
        response = self._request(
            "POST",
            "/sell/account/v1/return_policy",
            payload=payload,
            expected_statuses=(200, 201),
            include_language=True,
        )
        return response.json() or {}

    def ensure_business_policies(self) -> dict[str, str]:
        try:
            return self.resolve_listing_policies()
        except EbayAPIError:
            auto_create = os.getenv("EBAY_AUTO_CREATE_POLICIES", "false").lower() in ("1", "true", "yes", "t")
            if not auto_create:
                raise

            # Best effort creation; re-resolve to produce authoritative IDs.
            self.create_default_payment_policy()
            self.create_default_fulfillment_policy()
            self.create_default_return_policy()
            self._policy_cache = None
            return self.resolve_listing_policies()

    def bootstrap_inventory_readiness(self) -> dict[str, Any]:
        """Best-effort readiness flow: auth, opt-in, policies, and location."""
        report: dict[str, Any] = {
            "token_ok": False,
            "rest_access_ok": False,
            "seller_registration_completed": False,
            "opt_in": None,
            "policy_ids_detected": None,
            "resolved_policy_ids": None,
            "location_key": None,
            "errors": [],
        }

        report["token_ok"] = bool(self.get_access_token())
        if not report["token_ok"]:
            report["errors"].append("Unable to acquire eBay access token")
            return report

        report["rest_access_ok"] = self.validate_rest_access()

        privilege = self.check_seller_registration()
        report["seller_registration_completed"] = privilege.get("sellerRegistrationCompleted", False)
        if not report["seller_registration_completed"]:
            msg = (
                "Seller registration shows as incomplete (sellerRegistrationCompleted=false). "
            )
            if Config.EBAY_SANDBOX_MODE:
                msg += (
                    "This is a known eBay sandbox limitation — the sandbox does not support "
                    "Managed Payments seller onboarding. Publishing may still work; "
                    "the app will attempt it regardless."
                )
                report.setdefault("warnings", []).append(msg)
            else:
                msg += (
                    "Publishing will fail until registration is finished. "
                    "Log in at https://www.ebay.com and complete the seller onboarding flow."
                )
                report["errors"].append(msg)

        try:
            report["opt_in"] = self.opt_in_to_program()
        except Exception as exc:
            report["opt_in"] = {"error": str(exc)}

        try:
            report["policy_ids_detected"] = self.list_policy_ids()
        except Exception as exc:
            report["errors"].append(f"Policy discovery failed: {exc}")

        try:
            report["resolved_policy_ids"] = self.ensure_business_policies()
        except Exception as exc:
            report["errors"].append(f"Policy resolution failed: {exc}")

        try:
            report["location_key"] = self.ensure_location_key()
        except Exception as exc:
            report["errors"].append(f"Location resolution failed: {exc}")

        return report

    def opt_in_to_program(self, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Call Sell Account opt-in endpoint for marketplace program enrollment."""
        request_payload = payload or {
            "programType": os.getenv("EBAY_OPT_IN_PROGRAM_TYPE", "SELLING_POLICY_MANAGEMENT")
        }
        response = self._request(
            "POST",
            "/sell/account/v1/program/opt_in",
            payload=request_payload,
            expected_statuses=(200, 201, 204),
        )
        if response.status_code == 204:
            return {"status": "ok", "program": request_payload}
        try:
            parsed = response.json()
        except ValueError:
            parsed = None
        return parsed or {"status": "ok", "program": request_payload, "status_code": response.status_code}

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
                # Attempt one-time opt-in recovery for sandbox accounts that need explicit enrollment.
                # This follows eBay Sell Account guidance around program/opt_in prior to policy usage.
                if os.getenv("EBAY_AUTO_OPT_IN", "false").lower() in ("true", "1", "t", "yes"):
                    try:
                        self.opt_in_to_program()
                        response = self._request(
                            "GET",
                            path,
                            params={"marketplace_id": self.marketplace_id},
                            expected_statuses=(200,),
                        )
                    except Exception:
                        raise EbayAPIError(
                            "This sandbox account is not eligible for eBay business policies. "
                            "Configure policy IDs explicitly, opt in via /sell/account/v1/program/opt_in, "
                            "or switch to an inventory-enabled sandbox seller account."
                        ) from exc
                else:
                    raise EbayAPIError(
                        "This sandbox account is not eligible for eBay business policies. "
                        "Configure policy IDs explicitly, opt in via /sell/account/v1/program/opt_in, "
                        "or switch to an inventory-enabled sandbox seller account."
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
        policies = self.ensure_business_policies()
        location_key = self.ensure_location_key()
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
        # Pre-flight: check seller registration status.
        # In sandbox mode, eBay may permanently report sellerRegistrationCompleted=false
        # because the sandbox doesn't support the Managed Payments onboarding flow.
        # We log a warning but still attempt the publish.
        skip_check = os.getenv("EBAY_SKIP_REGISTRATION_CHECK", "").strip().lower() in ("true", "1", "t")
        if not skip_check:
            privilege = self.check_seller_registration()
            if not privilege.get("sellerRegistrationCompleted"):
                if not Config.EBAY_SANDBOX_MODE:
                    # In production, this is a hard blocker.
                    raise EbayAPIError(
                        "Cannot publish: seller registration is not complete on this production account. "
                        "Log in at https://www.ebay.com and complete the seller onboarding flow."
                    )
                # In sandbox, warn but proceed — the sandbox may not support seller registration.
                import logging
                logging.getLogger(__name__).warning(
                    "Sandbox seller registration is incomplete (sellerRegistrationCompleted=false). "
                    "This is a known eBay sandbox limitation. Attempting publish anyway."
                )

        retries = int(os.getenv("EBAY_PUBLISH_RETRIES", "3"))
        delay_seconds = float(os.getenv("EBAY_PUBLISH_RETRY_DELAY_SECONDS", "2"))
        transient_markers = (
            "system error",
            "please try again later",
            "internal error",
            "temporarily unavailable",
        )

        last_error: Optional[Exception] = None
        for attempt in range(retries):
            try:
                response = self._request(
                    "POST",
                    f"/sell/inventory/v1/offer/{offer_id}/publish",
                    expected_statuses=(200,),
                    include_language=True,
                )
                payload = response.json() or {}
                return EbayListingState(
                    sku=payload.get("sku") or "",
                    offer_id=payload.get("offerId") or offer_id,
                    listing_id=payload.get("listingId"),
                    status="PUBLISHED",
                    marketplace_id=self.marketplace_id,
                )
            except EbayAPIError as exc:
                last_error = exc
                message = str(exc).lower()
                is_transient = any(marker in message for marker in transient_markers)
                if is_transient and attempt < retries - 1:
                    time.sleep(delay_seconds * (attempt + 1))
                    continue
                if is_transient:
                    try:
                        states = self.bulk_publish_offers([offer_id])
                        if states:
                            return states[0]
                    except Exception:
                        pass
                raise

        if last_error:
            raise last_error
        raise EbayAPIError("Unable to publish eBay offer")

    def bulk_publish_offers(self, offer_ids: list[str]) -> list[EbayListingState]:
        response = self._request(
            "POST",
            "/sell/inventory/v1/bulk_publish_offer",
            payload={"requests": [{"offerId": offer_id} for offer_id in offer_ids]},
            expected_statuses=(200,),
            include_language=True,
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
