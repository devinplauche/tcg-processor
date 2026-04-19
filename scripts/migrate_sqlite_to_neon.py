#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import psycopg
from psycopg.rows import dict_row


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DB = REPO_ROOT / "frontend" / "mtg-inventory" / "mtg_inventory.db"


@dataclass
class MinimalCard:
    source_id: int
    scryfall_id: str
    name: str
    set_code: str
    set_name: str
    collector_number: str
    foil: bool
    rarity: str
    quantity: int
    condition: str
    language: str
    purchase_price: float
    created_at: str | None
    updated_at: str | None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy a minimal subset of the local SQLite MTG inventory into Neon Postgres."
    )
    parser.add_argument(
        "--source-db",
        default=str(DEFAULT_SOURCE_DB),
        help="Path to the SQLite source database.",
    )
    parser.add_argument(
        "--target-url",
        default=os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL"),
        help="Target Postgres connection string. Defaults to NEON_DATABASE_URL or DATABASE_URL.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("MINIMAL_NEON_CARD_LIMIT", "25")),
        help="Maximum number of aggregated card rows to import.",
    )
    parser.add_argument(
        "--box-capacity",
        type=int,
        default=int(os.getenv("BOX_CAPACITY", "500")),
        help="Box capacity value to store in the target database.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate the target tables before inserting data.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and print the selected rows without writing to Postgres.",
    )
    return parser.parse_args()


def _normalize_target_url(target_url: str | None) -> str:
    if not target_url:
        raise SystemExit("A Postgres target URL is required via --target-url, NEON_DATABASE_URL, or DATABASE_URL.")
    if target_url.startswith("postgresql+psycopg://"):
        return "postgresql://" + target_url[len("postgresql+psycopg://") :]
    if target_url.startswith("postgres://"):
        return "postgresql://" + target_url[len("postgres://") :]
    return target_url


def _select_minimal_cards(source_db: Path, limit: int) -> list[MinimalCard]:
    conn = sqlite3.connect(source_db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            WITH aggregated AS (
                SELECT
                    MIN(id) AS source_id,
                    COALESCE(NULLIF(TRIM(MAX(scryfall_id)), ''), 'legacy-' || MIN(id)) AS scryfall_id,
                    TRIM(name) AS name,
                    COALESCE(NULLIF(TRIM(set_code), ''), 'UNK') AS set_code,
                    COALESCE(NULLIF(TRIM(MAX(set_name)), ''), COALESCE(NULLIF(TRIM(set_code), ''), 'Unknown Set')) AS set_name,
                    COALESCE(NULLIF(TRIM(MAX(collector_number)), ''), CAST(MIN(id) AS TEXT)) AS collector_number,
                    COALESCE(MAX(CAST(foil AS INTEGER)), 0) AS foil,
                    COALESCE(NULLIF(TRIM(MAX(rarity)), ''), 'unknown') AS rarity,
                    CAST(SUM(COALESCE(quantity, 1)) AS INTEGER) AS quantity,
                    COALESCE(NULLIF(TRIM(condition), ''), 'Near Mint') AS card_condition,
                    COALESCE(NULLIF(TRIM(MAX(language)), ''), 'en') AS language,
                    ROUND(AVG(COALESCE(purchase_price, 0)), 2) AS purchase_price,
                    MIN(created_at) AS created_at,
                    MAX(updated_at) AS updated_at
                FROM cards
                WHERE name IS NOT NULL AND TRIM(name) <> ''
                GROUP BY TRIM(name), COALESCE(NULLIF(TRIM(set_code), ''), 'UNK'), COALESCE(NULLIF(TRIM(condition), ''), 'Near Mint'), COALESCE(CAST(foil AS INTEGER), 0)
            )
            SELECT *
            FROM aggregated
            ORDER BY quantity DESC, name ASC, set_code ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    cards: list[MinimalCard] = []
    for row in rows:
        cards.append(
            MinimalCard(
                source_id=int(row["source_id"]),
                scryfall_id=str(row["scryfall_id"]),
                name=str(row["name"]),
                set_code=str(row["set_code"]),
                set_name=str(row["set_name"]),
                collector_number=str(row["collector_number"]),
                foil=bool(row["foil"]),
                rarity=str(row["rarity"]),
                quantity=int(row["quantity"] or 1),
                condition=str(row["card_condition"]),
                language=str(row["language"]),
                purchase_price=float(row["purchase_price"] or 0.0),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )
    return cards


def _create_schema(cur: psycopg.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS boxes (
            box_number INTEGER PRIMARY KEY,
            capacity INTEGER DEFAULT 500,
            current_count INTEGER DEFAULT 0,
            qr_code_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            scryfall_id TEXT UNIQUE NOT NULL,
            manabox_id TEXT,
            name TEXT NOT NULL,
            set_code TEXT,
            set_name TEXT,
            collector_number TEXT,
            foil BOOLEAN DEFAULT FALSE,
            rarity TEXT,
            quantity INTEGER DEFAULT 1,
            condition TEXT,
            language TEXT DEFAULT 'en',
            purchase_price DOUBLE PRECISION,
            location_code TEXT,
            box_number INTEGER REFERENCES boxes(box_number),
            slot_number INTEGER,
            list_on_ebay BOOLEAN DEFAULT FALSE,
            ebay_offer_id TEXT,
            ebay_listing_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            sync_type TEXT,
            status TEXT,
            cards_processed INTEGER,
            errors INTEGER,
            run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS import_card_links (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            sync_log_id INTEGER NOT NULL REFERENCES sync_log(id) ON DELETE CASCADE,
            card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            scryfall_id TEXT NOT NULL REFERENCES cards(scryfall_id) ON DELETE CASCADE,
            market_price DOUBLE PRECISION,
            low_price DOUBLE PRECISION,
            high_price DOUBLE PRECISION,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def _reset_schema(cur: psycopg.Cursor) -> None:
    cur.execute(
        """
        DROP TABLE IF EXISTS import_card_links;
        DROP TABLE IF EXISTS prices;
        DROP TABLE IF EXISTS sync_log;
        DROP TABLE IF EXISTS cards;
        DROP TABLE IF EXISTS boxes;
        """
    )


def _insert_cards(
    cur: psycopg.Cursor,
    cards: Iterable[MinimalCard],
    *,
    box_capacity: int,
    limit: int,
) -> dict[str, int]:
    card_ids: list[int] = []
    card_list = list(cards)

    cur.execute(
        """
        INSERT INTO boxes (box_number, capacity, current_count)
        VALUES (%s, %s, %s)
        ON CONFLICT (box_number) DO UPDATE
        SET capacity = EXCLUDED.capacity,
            current_count = EXCLUDED.current_count
        """,
        (1, box_capacity, len(card_list)),
    )

    for index, card in enumerate(card_list, start=1):
        location_code = f"BOX-0001-SLOT-{index:04d}"
        cur.execute(
            """
            INSERT INTO cards (
                scryfall_id,
                manabox_id,
                name,
                set_code,
                set_name,
                collector_number,
                foil,
                rarity,
                quantity,
                condition,
                language,
                purchase_price,
                location_code,
                box_number,
                slot_number,
                list_on_ebay,
                ebay_offer_id,
                ebay_listing_id,
                created_at,
                updated_at
            )
            VALUES (
                %(scryfall_id)s,
                NULL,
                %(name)s,
                %(set_code)s,
                %(set_name)s,
                %(collector_number)s,
                %(foil)s,
                %(rarity)s,
                %(quantity)s,
                %(condition)s,
                %(language)s,
                %(purchase_price)s,
                %(location_code)s,
                1,
                %(slot_number)s,
                FALSE,
                NULL,
                NULL,
                COALESCE(%(created_at)s::timestamp, CURRENT_TIMESTAMP),
                COALESCE(%(updated_at)s::timestamp, CURRENT_TIMESTAMP)
            )
            RETURNING id
            """,
            {
                "scryfall_id": card.scryfall_id,
                "name": card.name,
                "set_code": card.set_code,
                "set_name": card.set_name,
                "collector_number": card.collector_number,
                "foil": card.foil,
                "rarity": card.rarity,
                "quantity": card.quantity,
                "condition": card.condition,
                "language": card.language,
                "purchase_price": card.purchase_price,
                "location_code": location_code,
                "slot_number": index,
                "created_at": card.created_at,
                "updated_at": card.updated_at,
            },
        )
        card_ids.append(int(cur.fetchone()["id"]))

    cur.execute(
        """
        INSERT INTO sync_log (sync_type, status, cards_processed, errors)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        ("minimal_neon_seed", "complete", len(card_list), 0),
    )
    sync_log_id = int(cur.fetchone()["id"])

    for card_id in card_ids:
        cur.execute(
            """
            INSERT INTO import_card_links (sync_log_id, card_id, status)
            VALUES (%s, %s, %s)
            """,
            (sync_log_id, card_id, "seeded"),
        )

    return {"cards": len(card_list), "boxes": 1, "sync_logs": 1, "limit": limit}


def _verify_target(cur: psycopg.Cursor) -> dict[str, int]:
    summary: dict[str, int] = {}
    for table_name in ("boxes", "cards", "sync_log", "import_card_links", "prices"):
        cur.execute(f"SELECT COUNT(*) AS count FROM {table_name}")
        summary[table_name] = int(cur.fetchone()["count"])
    return summary


def main() -> None:
    args = _parse_args()
    source_db = Path(args.source_db).resolve()
    if not source_db.exists():
        raise SystemExit(f"Source database not found: {source_db}")

    cards = _select_minimal_cards(source_db, args.limit)
    if not cards:
        raise SystemExit("No cards were selected from the SQLite source database.")

    print(f"Selected {len(cards)} aggregated card rows from {source_db}.")
    for card in cards[: min(5, len(cards))]:
        print(f" - {card.name} [{card.set_code}] x{card.quantity}")

    if args.dry_run:
        return

    target_url = _normalize_target_url(args.target_url)
    with psycopg.connect(target_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            if args.reset:
                _reset_schema(cur)
            _create_schema(cur)
            if args.reset:
                conn.commit()
            summary = _insert_cards(cur, cards, box_capacity=args.box_capacity, limit=args.limit)
        conn.commit()

        with conn.cursor() as cur:
            verification = _verify_target(cur)

    print("Migration complete.")
    print(f"Seeded summary: {summary}")
    print(f"Verified row counts: {verification}")


if __name__ == "__main__":
    main()
