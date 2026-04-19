import os
import logging
import secrets
from pathlib import Path
from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent
load_dotenv(_BASE_DIR / ".env")
load_dotenv(_BASE_DIR / ".env.local", override=True)

logger = logging.getLogger(__name__)


def parse_bool_env(varname: str, default: str = "false") -> bool:
    """Parse boolean-like environment values using common truthy forms."""
    return os.getenv(varname, default).strip().lower() in ("true", "1", "t")

class Config:
    BOX_CAPACITY = int(os.getenv("BOX_CAPACITY", 500))
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///mtg_inventory.db")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    _configured_secret = os.getenv("FLASK_SECRET_KEY")
    if _configured_secret:
        FLASK_SECRET_KEY = _configured_secret
    elif FLASK_ENV == "development":
        FLASK_SECRET_KEY = secrets.token_urlsafe(32)
        logger.warning("FLASK_SECRET_KEY is not set; using an ephemeral development-only secret.")
    else:
        raise RuntimeError("FLASK_SECRET_KEY environment variable is required outside development")
    BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")

    # eBay API Config
    # Prefer EBAY_CLIENT_ID; EBAY_APP_ID remains a one-way alias for compatibility.
    EBAY_CLIENT_ID = os.getenv("EBAY_CLIENT_ID") or os.getenv("EBAY_APP_ID")
    EBAY_APP_ID = os.getenv("EBAY_APP_ID") or EBAY_CLIENT_ID
    EBAY_DEV_ID = os.getenv("EBAY_DEV_ID")
    EBAY_USER_TOKEN = os.getenv("EBAY_USER_TOKEN")
    EBAY_CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET")
    EBAY_REFRESH_TOKEN = os.getenv("EBAY_REFRESH_TOKEN")
    # os.getenv returns strings; treat "true", "1", and "t" (case-insensitive) as True.
    EBAY_SANDBOX_MODE = parse_bool_env("EBAY_SANDBOX_MODE", "True")
    EBAY_MARKETPLACE_ID = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US")
    EBAY_CATEGORY_ID = os.getenv("EBAY_CATEGORY_ID", "183454")
    EBAY_CURRENCY = os.getenv("EBAY_CURRENCY", "USD")
    EBAY_CONTENT_LANGUAGE = os.getenv("EBAY_CONTENT_LANGUAGE", "en-US")
    EBAY_MERCHANT_LOCATION_KEY = os.getenv("EBAY_MERCHANT_LOCATION_KEY")
    EBAY_PAYMENT_POLICY_ID = os.getenv("EBAY_PAYMENT_POLICY_ID")
    EBAY_FULFILLMENT_POLICY_ID = os.getenv("EBAY_FULFILLMENT_POLICY_ID")
    EBAY_RETURN_POLICY_ID = os.getenv("EBAY_RETURN_POLICY_ID")
