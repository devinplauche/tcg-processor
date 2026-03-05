import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOX_CAPACITY = int(os.getenv("BOX_CAPACITY", 500))
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///mtg_inventory.db")
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "a_default_secret_key")
    BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
    
    # eBay API Config
    EBAY_CLIENT_ID = os.getenv("EBAY_CLIENT_ID")
    EBAY_CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET")
    EBAY_REFRESH_TOKEN = os.getenv("EBAY_REFRESH_TOKEN")
    EBAY_SANDBOX_MODE = os.getenv("EBAY_SANDBOX_MODE", "True").lower() in ('true', '1', 't')

    # TCGPlayer API Config
    TCGPLAYER_API_KEY = os.getenv("TCGPLAYER_API_KEY")
    TCGPLAYER_API_SECRET = os.getenv("TCGPLAYER_API_SECRET")
