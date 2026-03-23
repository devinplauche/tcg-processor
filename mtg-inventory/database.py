import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Get the database URL from environment or construct a default one
DATABASE_URL = os.getenv("DATABASE_URL")

# If DATABASE_URL uses relative path (sqlite:///), convert to absolute path
if DATABASE_URL and "sqlite:///" in DATABASE_URL:
    # Extract the relative path part (e.g., "mtg_inventory.db" from "sqlite:///mtg_inventory.db")
    relative_path = DATABASE_URL.replace("sqlite:///", "")
    # Get the directory where this database.py file is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Create absolute path to database file
    absolute_db_path = os.path.join(current_dir, relative_path)
    # Update DATABASE_URL to use absolute path
    DATABASE_URL = f"sqlite:///{absolute_db_path}"
elif not DATABASE_URL:
    # Default: create database in the same directory as database.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    absolute_db_path = os.path.join(current_dir, "mtg_inventory.db")
    DATABASE_URL = f"sqlite:///{absolute_db_path}"

print(f"[Database] Using: {DATABASE_URL}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    from models import Card, Price, Box, SyncLog, ImportCardLink
    Base.metadata.create_all(bind=engine)
