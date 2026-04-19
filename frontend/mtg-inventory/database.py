import os
from sqlalchemy import text
from sqlalchemy import inspect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)


def _normalize_database_url(database_url: str | None) -> str:
    if not database_url:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        absolute_db_path = os.path.join(current_dir, "mtg_inventory.db")
        return f"sqlite:///{absolute_db_path}"

    if database_url.startswith("sqlite:///"):
        relative_path = database_url[len("sqlite:///"):]
        if not relative_path.startswith("/"):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            absolute_db_path = os.path.join(current_dir, relative_path)
            return f"sqlite:///{absolute_db_path}"
        return database_url

    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)

    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return database_url


# Get the database URL from environment or construct a default one
DATABASE_URL = _normalize_database_url(os.getenv("DATABASE_URL"))

print(f"[Database] Using: {DATABASE_URL}")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
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
