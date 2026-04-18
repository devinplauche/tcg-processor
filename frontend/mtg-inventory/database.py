import os
from sqlalchemy import text
from sqlalchemy import inspect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

# Get the database URL from environment or construct a default one
DATABASE_URL = os.getenv("DATABASE_URL")

# If DATABASE_URL uses a relative sqlite path, convert it to an absolute path.
if DATABASE_URL and DATABASE_URL.startswith("sqlite:///"):
    relative_path = DATABASE_URL[len("sqlite:///"):]
    if not relative_path.startswith("/"):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        absolute_db_path = os.path.join(current_dir, relative_path)
        DATABASE_URL = f"sqlite:///{absolute_db_path}"
elif not DATABASE_URL:
    # Default: create database in the same directory as database.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    absolute_db_path = os.path.join(current_dir, "mtg_inventory.db")
    DATABASE_URL = f"sqlite:///{absolute_db_path}"

print(f"[Database] Using: {DATABASE_URL}")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    from models import Card, Price, Box, SyncLog, ImportCardLink
    Base.metadata.create_all(bind=engine)
    _ensure_cards_columns()


def _ensure_cards_columns():
    required_columns = {
        "ebay_offer_id": "ALTER TABLE cards ADD COLUMN ebay_offer_id TEXT",
    }
    with engine.begin() as connection:
        try:
            inspector = inspect(connection)
            columns = {col["name"] for col in inspector.get_columns("cards")}
        except Exception as exc:
            logger.exception("Unable to inspect cards table columns: %s", exc)
            return
        for column_name, ddl in required_columns.items():
            if column_name not in columns:
                connection.execute(text(ddl))
