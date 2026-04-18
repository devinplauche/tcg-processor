"""Quick real-connection diagnostics for Google Drive, LangChain, and eBay."""

from __future__ import annotations

import json
import os
from pathlib import Path

from services.ebay_api import EbayAPIError, eBayAPI


def check_google_credentials() -> None:
    credentials_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS_JSON", "").strip()
    print("\n[Google Drive]")
    if not credentials_path:
        print("- GOOGLE_DRIVE_CREDENTIALS_JSON is not set")
        return

    path = Path(credentials_path).expanduser()
    if not path.exists():
        print(f"- Credentials file not found: {path}")
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"- Error: malformed credentials JSON: {exc}")
        return
    if payload.get("type") == "service_account":
        print("- Credentials type: service_account")
    elif "installed" in payload or "web" in payload:
        print("- Credentials type: OAuth client (installed/web)")
        print("- This app will use OAuth consent and store token in GOOGLE_DRIVE_TOKEN_JSON")
    else:
        print("- Credentials type: unsupported JSON shape")

    print(f"- Target folder: {os.getenv('GOOGLE_DRIVE_TARGET_FOLDER_URL', '(not configured)')}")


def check_langchain_config() -> None:
    print("\n[LangChain Scanner]")
    endpoint = os.getenv("LANGCHAIN_SCANNER_ENDPOINT", "").strip()
    script_path = os.getenv("LANGCHAIN_SCANNER_SCRIPT_PATH", "").strip()

    if endpoint:
        print(f"- Endpoint mode: {endpoint}")
    else:
        print("- Endpoint mode: not configured (will use local scanner script fallback)")

    if script_path:
        print(f"- Local scanner script: {script_path}")
    else:
        print("- Local scanner script: default backend/compute/langchain/langchain_scan_cards.py")


def check_ebay() -> None:
    print("\n[eBay]")
    api = eBayAPI()

    token_ok = bool(api.get_access_token())
    print(f"- Access token available: {token_ok}")
    if not token_ok:
        print("- Fix EBAY_* credentials first")
        return

    rest_ok = api.validate_rest_access()
    print(f"- Sell Account REST access: {rest_ok} (status={api._last_auth_status})")

    try:
        policies = api.resolve_listing_policies()
        print(f"- Business policies ready: {bool(policies)}")
    except EbayAPIError as exc:
        print(f"- Business policies failed: {exc}")
        print("- Attempting program opt-in via /sell/account/v1/program/opt_in ...")
        try:
            result = api.opt_in_to_program()
            print(f"- Opt-in response: {result}")
        except EbayAPIError as opt_exc:
            print(f"- Opt-in failed: {opt_exc}")

    try:
        location = api.resolve_location_key()
        print(f"- Merchant location key: {location}")
    except EbayAPIError as exc:
        print(f"- Merchant location failed: {exc}")


if __name__ == "__main__":
    print("Live integration diagnostics")
    check_google_credentials()
    check_langchain_config()
    check_ebay()
