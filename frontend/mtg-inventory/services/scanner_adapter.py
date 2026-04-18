"""
Scanner CSV adapter.

Converts CSV output from the backend LangChain card scanner
(backend/compute/langchain/langchain_scan_cards.py) into the column layout
expected by services.manabox.import_csv.

Scanner columns:
    filename, card_name, set_name, set_code, colors, mana_cost, type_line,
    rarity, power_toughness, confidence, status, error, timestamp

Importer required columns:
    name, set_code, set_name, collector_number, foil, rarity, quantity,
    manabox_id, scryfall_id, purchase_price, condition, language
"""
from __future__ import annotations

import uuid

import pandas as pd

# Namespace for deterministic synthetic Scryfall IDs generated from scanner data.
# Using a fixed UUID5 namespace so the same card always maps to the same ID.
_SYNTHETIC_ID_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def is_scanner_csv(df: pd.DataFrame) -> bool:
    """Return True if *df* looks like output from the LangChain card scanner.

    Detection heuristic: the scanner always emits a ``card_name`` column,
    which the ManaBox format never uses.
    """
    if df.empty and len(df.columns) == 0:
        return False
    return "card_name" in df.columns


def normalize_scanner_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Transform a scanner CSV DataFrame into a shape importable by manabox.import_csv.

    Steps:
    1. Keep only rows where ``status == 'success'``.
    2. Rename ``card_name`` → ``name``.
    3. Fill missing required columns with sensible defaults.
    4. Generate a deterministic synthetic ``scryfall_id`` from ``name + set_code``
       so that re-importing the same scan updates rather than duplicates.
    """
    # 1. Filter to successful scans only; treat missing status as non-success.
    if "status" in df.columns:
        df = df[df["status"].str.lower().fillna("") == "success"].copy()
    else:
        df = df.copy()

    if df.empty:
        return pd.DataFrame(columns=[
            "name", "set_code", "set_name", "collector_number", "foil",
            "rarity", "quantity", "manabox_id", "scryfall_id",
            "purchase_price", "condition", "language",
        ])

    # 2. Rename card_name → name
    df = df.rename(columns={"card_name": "name"})

    # 3. Fill defaults for required-but-missing columns
    defaults: dict = {
        "collector_number": "",
        "foil": "normal",
        "quantity": 1,
        "manabox_id": None,
        "purchase_price": None,
        "condition": "Near Mint",
        "language": "en",
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    # 4. Generate deterministic synthetic scryfall_id from name + set_code + collector_number
    def _synthetic_id(row: pd.Series) -> str:
        name = str(row.get("name", "")).strip().lower()
        set_code = str(row.get("set_code", "")).strip().lower()
        collector_number = str(row.get("collector_number", "")).strip().lower()
        key = f"{name}::{set_code}::{collector_number}"
        return str(uuid.uuid5(_SYNTHETIC_ID_NAMESPACE, key))

    df["scryfall_id"] = df.apply(_synthetic_id, axis=1)

    return df.reset_index(drop=True)
