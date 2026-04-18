import os
from pathlib import Path
from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent
load_dotenv(_BASE_DIR / ".env")
load_dotenv(_BASE_DIR / ".env.local", override=True)

class Config:
    BOX_CAPACITY = int(os.getenv("BOX_CAPACITY", 500))
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///mtg_inventory.db")
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "a_default_secret_key")
    BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
    
    # eBay API Config (primary: APP/DEV/USER token; legacy vars still supported)
    EBAY_APP_ID = os.getenv("EBAY_APP_ID") or os.getenv("EBAY_CLIENT_ID")
    EBAY_DEV_ID = os.getenv("EBAY_DEV_ID")
    EBAY_USER_TOKEN = os.getenv("EBAY_USER_TOKEN") or os.getenv("EBAY_REFRESH_TOKEN")
    EBAY_CLIENT_ID = EBAY_APP_ID
    EBAY_CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET")
    EBAY_REFRESH_TOKEN = EBAY_USER_TOKEN
    EBAY_SANDBOX_MODE = os.getenv("EBAY_SANDBOX_MODE", "True").lower() in ('true', '1', 't')
