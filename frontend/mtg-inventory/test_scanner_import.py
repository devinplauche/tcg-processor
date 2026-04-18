"""
TDD tests for scanner CSV → inventory import adapter.

These tests verify that CSV output from the backend LangChain card scanner
(backend/compute/langchain/langchain_scan_cards.py) can be ingested by the
frontend import pipeline without manual column editing.

The scanner produces these columns:
    filename, card_name, set_name, set_code, colors, mana_cost, type_line,
    rarity, power_toughness, confidence, status, error, timestamp

The inventory importer (manabox.import_csv) expects these columns:
    name, set_code, set_name, collector_number, foil, rarity, quantity,
    manabox_id, scryfall_id, purchase_price, condition, language
"""
import sys
import os
import pytest
from io import BytesIO

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from services.scanner_adapter import is_scanner_csv, normalize_scanner_csv
from services.manabox import import_csv
from models import Card


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCANNER_COLUMNS = [
    "filename", "card_name", "set_name", "set_code", "colors", "mana_cost",
    "type_line", "rarity", "power_toughness", "confidence", "status", "error",
    "timestamp",
]

MANABOX_COLUMNS = [
    "Name", "Set code", "Set name", "Collector number", "Foil", "Rarity",
    "Quantity", "ManaBox ID", "Scryfall ID", "Purchase price", "Condition",
    "Language",
]


def make_scanner_csv(**overrides) -> BytesIO:
    """Return a BytesIO containing a scanner CSV.

    Pass keyword arguments to override specific columns.  All lists must be
    the same length.  The default produces a two-row CSV; pass single-element
    lists to produce a one-row CSV.
    """
    # Determine row count from the first override that is a list, defaulting to 2.
    n = 2
    for v in overrides.values():
        if isinstance(v, list):
            n = len(v)
            break

    rows: dict = {
        "filename": [f"card_{i:03d}.jpg" for i in range(1, n + 1)],
        "card_name": (["Lightning Bolt", "Counterspell"] * n)[:n],
        "set_name": (["Limited Edition Alpha"] * n)[:n],
        "set_code": (["LEA"] * n)[:n],
        "colors": (["R", "U"] * n)[:n],
        "mana_cost": (["{R}", "{U}{U}"] * n)[:n],
        "type_line": (["Instant"] * n)[:n],
        "rarity": (["common"] * n)[:n],
        "power_toughness": ([None] * n)[:n],
        "confidence": ([0.95, 0.88] * n)[:n],
        "status": (["success"] * n)[:n],
        "error": ([""] * n)[:n],
        "timestamp": ([f"2026-04-18T10:00:{i:02d}" for i in range(n)])[:n],
    }
    rows.update(overrides)
    buf = BytesIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    buf.seek(0)
    return buf


def make_manabox_csv() -> BytesIO:
    """Return a minimal valid ManaBox CSV."""
    rows = {
        "Name": ["Path to Exile"],
        "Set code": ["SLD"],
        "Set name": ["Secret Lair Drop"],
        "Collector number": ["226"],
        "Foil": ["normal"],
        "Rarity": ["rare"],
        "Quantity": [1],
        "ManaBox ID": ["64698"],
        "Scryfall ID": ["4e2fe951-4820-4555-8cee-621c66ed8620"],
        "Purchase price": [15.27],
        "Condition": ["near_mint"],
        "Language": ["en"],
    }
    buf = BytesIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# is_scanner_csv
# ---------------------------------------------------------------------------

class TestIsScannerCsv:
    def test_detects_scanner_format_by_card_name_column(self):
        df = pd.read_csv(make_scanner_csv())
        assert is_scanner_csv(df) is True

    def test_rejects_manabox_format(self):
        df = pd.read_csv(make_manabox_csv())
        assert is_scanner_csv(df) is False

    def test_rejects_empty_dataframe(self):
        df = pd.DataFrame()
        assert is_scanner_csv(df) is False

    def test_detects_scanner_even_when_optional_columns_missing(self):
        """A minimal scanner export (just card_name + status) is still scanner format."""
        df = pd.DataFrame({"card_name": ["Bolt"], "status": ["success"]})
        assert is_scanner_csv(df) is True


# ---------------------------------------------------------------------------
# normalize_scanner_csv
# ---------------------------------------------------------------------------

class TestNormalizeScannerCsv:
    def test_renames_card_name_to_name(self):
        df = pd.read_csv(make_scanner_csv())
        out = normalize_scanner_csv(df)
        assert "name" in out.columns
        assert "card_name" not in out.columns

    def test_name_values_are_preserved(self):
        df = pd.read_csv(make_scanner_csv())
        out = normalize_scanner_csv(df)
        assert list(out["name"]) == ["Lightning Bolt", "Counterspell"]

    def test_filters_error_rows(self):
        """Rows where status != 'success' must be excluded."""
        df = pd.read_csv(
            make_scanner_csv(
                card_name=["Lightning Bolt", "Broken Card"],
                status=["success", "error"],
            )
        )
        out = normalize_scanner_csv(df)
        assert len(out) == 1
        assert out.iloc[0]["name"] == "Lightning Bolt"

    def test_adds_default_quantity(self):
        df = pd.read_csv(make_scanner_csv())
        out = normalize_scanner_csv(df)
        assert "quantity" in out.columns
        assert all(out["quantity"] == 1)

    def test_adds_default_condition(self):
        df = pd.read_csv(make_scanner_csv())
        out = normalize_scanner_csv(df)
        assert "condition" in out.columns
        assert all(out["condition"] == "Near Mint")

    def test_adds_default_language(self):
        df = pd.read_csv(make_scanner_csv())
        out = normalize_scanner_csv(df)
        assert "language" in out.columns
        assert all(out["language"] == "en")

    def test_adds_default_foil(self):
        df = pd.read_csv(make_scanner_csv())
        out = normalize_scanner_csv(df)
        assert "foil" in out.columns
        assert all(out["foil"] == "normal")

    def test_adds_default_collector_number(self):
        df = pd.read_csv(make_scanner_csv())
        out = normalize_scanner_csv(df)
        assert "collector_number" in out.columns
        assert all(out["collector_number"].isna() | (out["collector_number"] == ""))

    def test_generates_deterministic_scryfall_id(self):
        """Same card_name + set_code must always produce the same synthetic scryfall_id."""
        df1 = pd.read_csv(make_scanner_csv())
        df2 = pd.read_csv(make_scanner_csv())
        out1 = normalize_scanner_csv(df1)
        out2 = normalize_scanner_csv(df2)
        assert list(out1["scryfall_id"]) == list(out2["scryfall_id"])

    def test_scryfall_id_differs_per_card(self):
        df = pd.read_csv(make_scanner_csv())
        out = normalize_scanner_csv(df)
        ids = list(out["scryfall_id"])
        assert ids[0] != ids[1], "Different cards must get different synthetic scryfall_ids"

    def test_scryfall_id_is_string(self):
        df = pd.read_csv(make_scanner_csv())
        out = normalize_scanner_csv(df)
        assert all(isinstance(v, str) for v in out["scryfall_id"])

    def test_all_required_importer_columns_present(self):
        required = [
            "name", "set_code", "set_name", "collector_number", "foil",
            "rarity", "quantity", "manabox_id", "scryfall_id",
            "purchase_price", "condition", "language",
        ]
        df = pd.read_csv(make_scanner_csv())
        out = normalize_scanner_csv(df)
        for col in required:
            assert col in out.columns, f"Missing column after normalization: {col}"

    def test_empty_success_rows_returns_empty_dataframe(self):
        df = pd.read_csv(
            make_scanner_csv(
                card_name=["Bad Card"],
                status=["error"],
            )
        )
        out = normalize_scanner_csv(df)
        assert len(out) == 0


# ---------------------------------------------------------------------------
# Full pipeline: import_csv accepts scanner CSV
# ---------------------------------------------------------------------------

class TestImportCsvWithScannerFormat:
    """
    Integration-style tests: scanner CSV flows through manabox.import_csv
    without raising 'Missing required column: name'.
    """

    @pytest.fixture
    def db(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
        Base.metadata.drop_all(bind=engine)

    def test_scanner_csv_does_not_raise_missing_column_error(self, db):
        csv_file = make_scanner_csv()
        # Must not raise ValueError("Missing required column: name")
        result = import_csv(db, csv_file)
        assert "added" in result

    def test_scanner_csv_adds_cards_to_db(self, db):
        csv_file = make_scanner_csv()
        result = import_csv(db, csv_file)
        assert result["added"] == 2
        assert result["skipped"] == 0

    def test_scanner_csv_cards_have_correct_names(self, db):
        csv_file = make_scanner_csv()
        import_csv(db, csv_file)
        cards = db.query(Card).order_by(Card.name).all()
        names = [c.name for c in cards]
        assert "Counterspell" in names
        assert "Lightning Bolt" in names

    def test_scanner_csv_cards_get_default_condition(self, db):
        csv_file = make_scanner_csv()
        import_csv(db, csv_file)
        cards = db.query(Card).all()
        assert all(c.condition == "Near Mint" for c in cards)

    def test_scanner_csv_error_rows_are_skipped(self, db):
        csv_file = make_scanner_csv(
            card_name=["Lightning Bolt", "Broken Scan"],
            status=["success", "error"],
        )
        result = import_csv(db, csv_file)
        assert result["added"] == 1
        cards = db.query(Card).all()
        assert cards[0].name == "Lightning Bolt"

    def test_reimport_same_scanner_csv_does_not_duplicate(self, db):
        """Deterministic scryfall_id means re-importing the same scan only updates."""
        csv_file = make_scanner_csv()
        import_csv(db, csv_file)
        csv_file.seek(0)
        import_csv(db, csv_file)
        cards = db.query(Card).all()
        assert len(cards) == 2, "Re-import must update, not duplicate"

    def test_same_card_twice_in_one_csv_increments_quantity(self, db):
        """Two rows with the same card in a single upload must not raise UNIQUE error
        and must result in quantity 2, not two separate rows."""
        csv_file = make_scanner_csv(
            card_name=["Lightning Bolt", "Lightning Bolt"],
            set_code=["LEA", "LEA"],
            colors=["R", "R"],
            mana_cost=["{R}", "{R}"],
            status=["success", "success"],
        )
        result = import_csv(db, csv_file)
        cards = db.query(Card).all()
        assert len(cards) == 1, "Duplicate card must be merged into one row"
        assert cards[0].quantity == 2, "Quantity must be summed across duplicate scans"

    def test_reimport_increments_quantity_not_replaces(self, db):
        """Re-importing a scanner CSV that was already imported must add quantity."""
        csv_file = make_scanner_csv(
            card_name=["Lightning Bolt"],
            set_code=["LEA"],
            status=["success"],
        )
        import_csv(db, csv_file)
        csv_file.seek(0)
        import_csv(db, csv_file)
        card = db.query(Card).first()
        assert card.quantity == 2, "Second import must increment quantity, not replace it"

    def test_manabox_csv_still_works_unchanged(self, db):
        """Existing ManaBox import path must be unaffected."""
        csv_file = make_manabox_csv()
        result = import_csv(db, csv_file)
        assert result["added"] == 1
        card = db.query(Card).first()
        assert card.name == "Path to Exile"
