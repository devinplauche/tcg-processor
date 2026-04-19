import pandas as pd
from models import Card
from services.location_engine import assign_location
from services.scanner_adapter import is_scanner_csv, normalize_scanner_csv

def import_csv(db, file):
    df = pd.read_csv(file)

    # Auto-detect scanner CSV format and normalise before column validation.
    # Scanner output uses 'card_name' and lacks many ManaBox columns; the
    # adapter renames and fills defaults so the rest of this function is
    # format-agnostic.
    scanner_import = is_scanner_csv(df)
    if scanner_import:
        df = normalize_scanner_csv(df)
    else:
        df.columns = [col.lower().replace(' ', '_') for col in df.columns]

    # Validate required columns
    required_columns = ['name', 'set_code', 'set_name', 'collector_number', 'foil', 'rarity', 'quantity', 'manabox_id', 'scryfall_id', 'purchase_price', 'condition', 'language']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    added_count = 0
    updated_count = 0
    skipped_count = 0
    status_by_scryfall_id = {}

    # Remove rows with missing or empty scryfall_id before aggregation so
    # they are counted as skipped rather than inserted with an empty key.
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(1).astype(int)
    df['scryfall_id'] = df['scryfall_id'].fillna('').astype(str).str.strip().str.lower()
    missing_mask = df['scryfall_id'] == ''
    skipped_count += int(missing_mask.sum())
    df = df[~missing_mask].copy()

    # Pre-aggregate rows that share the same scryfall_id within this batch
    # (e.g. the same card scanned twice in one session). Summing quantities
    # here avoids UNIQUE constraint errors from two INSERTs in the same tx.
    if not df.empty:
        df = (
            df.groupby('scryfall_id', as_index=False)
            .agg({**{col: 'first' for col in df.columns if col not in ('scryfall_id', 'quantity')}, 'quantity': 'sum'})
        )

    existing_cards_by_scryfall_id = {}
    if not df.empty:
        existing_cards = (
            db.query(Card)
            .filter(Card.scryfall_id.in_(df['scryfall_id'].tolist()))
            .all()
        )
        existing_cards_by_scryfall_id = {
            str(card.scryfall_id).strip().lower(): card for card in existing_cards
        }

    for _, row in df.iterrows():
        scryfall_id = row['scryfall_id']
        card = existing_cards_by_scryfall_id.get(scryfall_id)

        if card:
            # Scanner imports: each row is a physical card seen → accumulate stock.
            # ManaBox imports: the quantity field is the authoritative total → set it.
            if scanner_import:
                card.quantity = (card.quantity or 0) + int(row['quantity'])
            else:
                card.quantity = int(row['quantity'])
            card.condition = row['condition']
            updated_count += 1
            status_by_scryfall_id[str(scryfall_id)] = 'updated'
        else:
            # Convert foil field: 'normal' or empty = False, 'foil' or True = True
            foil_value = row.get('foil', False)
            if isinstance(foil_value, str):
                foil_value = foil_value.lower().strip() == 'foil'
            else:
                foil_value = bool(foil_value)
            
            # Convert manabox_id to string, handle NaN
            manabox_id = row.get('manabox_id')
            if pd.notna(manabox_id):
                manabox_id = str(int(manabox_id)) if isinstance(manabox_id, float) else str(manabox_id)
            else:
                manabox_id = None
            
            # Create new card
            new_card = Card(
                scryfall_id=scryfall_id,
                manabox_id=manabox_id,
                name=row['name'],
                set_code=row['set_code'],
                set_name=row['set_name'],
                collector_number=row['collector_number'],
                foil=foil_value,
                rarity=row.get('rarity'),
                quantity=int(row.get('quantity', 1)),
                condition=row.get('condition'),
                language=row.get('language', 'en'),
                purchase_price=row.get('purchase_price'),
            )
            # Assign location
            assign_location(db, new_card)
            db.add(new_card)
            db.flush()
            existing_cards_by_scryfall_id[scryfall_id] = new_card
            added_count += 1
            status_by_scryfall_id[str(scryfall_id)] = 'added'

    db.commit()

    preview = []
    import_cards = []
    if status_by_scryfall_id:
        imported_cards = (
            db.query(Card)
            .filter(Card.scryfall_id.in_(list(status_by_scryfall_id.keys())))
            .order_by(Card.updated_at.desc())
            .all()
        )

        for card in imported_cards[:8]:
            preview.append(
                {
                    'id': card.id,
                    'name': card.name,
                    'set_code': card.set_code,
                    'condition': card.condition,
                    'foil': bool(card.foil),
                    'quantity': card.quantity,
                    'location_code': card.location_code,
                    'status': status_by_scryfall_id.get(str(card.scryfall_id), 'updated'),
                }
            )

        import_cards = [
            {
                'card_id': card.id,
                'status': status_by_scryfall_id.get(str(card.scryfall_id), 'updated'),
            }
            for card in imported_cards
        ]
    
    return {
        "added": added_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "preview": preview,
        "import_cards": import_cards,
    }
