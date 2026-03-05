from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, TIMESTAMP, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Card(Base):
    __tablename__ = 'cards'
    id = Column(Integer, primary_key=True, autoincrement=True)
    scryfall_id = Column(Text, unique=True, nullable=False)
    manabox_id = Column(Text)
    name = Column(Text, nullable=False)
    set_code = Column(Text)
    set_name = Column(Text)
    collector_number = Column(Text)
    foil = Column(Boolean, default=False)
    rarity = Column(Text)
    quantity = Column(Integer, default=1)
    condition = Column(Text)
    language = Column(Text, default='en')
    purchase_price = Column(Float)
    location_code = Column(Text)
    box_number = Column(Integer)
    slot_number = Column(Integer)
    list_on_ebay = Column(Boolean, default=False)
    ebay_listing_id = Column(Text)
    tcgplayer_product_id = Column(Text)
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    prices = relationship("Price", back_populates="card")

class Price(Base):
    __tablename__ = 'prices'
    id = Column(Integer, primary_key=True, autoincrement=True)
    scryfall_id = Column(Text, ForeignKey('cards.scryfall_id'), nullable=False)
    market_price = Column(Float)
    low_price = Column(Float)
    high_price = Column(Float)
    fetched_at = Column(TIMESTAMP, default=func.now())
    card = relationship("Card", back_populates="prices")

class Box(Base):
    __tablename__ = 'boxes'
    box_number = Column(Integer, primary_key=True)
    capacity = Column(Integer, default=500)
    current_count = Column(Integer, default=0)
    qr_code_path = Column(Text)
    created_at = Column(TIMESTAMP, default=func.now())

class SyncLog(Base):
    __tablename__ = 'sync_log'
    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_type = Column(Text)
    status = Column(Text)
    cards_processed = Column(Integer)
    errors = Column(Integer)
    run_at = Column(TIMESTAMP, default=func.now())
