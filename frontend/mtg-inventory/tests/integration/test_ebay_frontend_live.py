import os
import sys

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from app import app


def _has_ebay_env() -> bool:
    return bool(
        os.getenv("EBAY_APP_ID")
        and os.getenv("EBAY_DEV_ID")
        and os.getenv("EBAY_USER_TOKEN")
    )


@pytest.mark.integration
def test_ebay_health_endpoint_live_reports_configuration():
    if not _has_ebay_env():
        pytest.skip("eBay credentials not configured for integration test")

    client = app.test_client()
    response = client.get("/api/ebay/health")

    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert data.get("configured") is True
    assert data.get("app_id_configured") is True
    assert data.get("dev_id_configured") is True
    assert data.get("user_token_configured") is True
    assert "token_ok" in data
    assert "auth_status_code" in data


@pytest.mark.integration
def test_ebay_live_credentials_authorize_sell_api():
    if not _has_ebay_env():
        pytest.skip("eBay credentials not configured for integration test")

    client = app.test_client()
    response = client.get("/api/ebay/health")
    assert response.status_code == 200

    data = response.get_json() or {}
    assert data.get("token_ok") is True, (
        "eBay credentials are configured but not accepted by Sell API. "
        f"auth_mode={data.get('auth_mode')} auth_status_code={data.get('auth_status_code')}"
    )