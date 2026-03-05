import pandas as pd
from models import Card
from services.location_engine import assign_location

def import_csv(db, file):
    df = pd.read_csv(file)
    df.columns = [col.lower().replace(' ', '_') for col in df.columns]
    print(df.columns)

    # Validate required columns
    required_columns = ['name', 'set_code', 'set_name', 'collector_number', 'foil', 'rarity', 'quantity', 'manabox_id', 'scryfall_id', 'purchase_price', 'condition', 'language']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    added_count = 0
    updated_count = 0
    skipped_count = 0

    for _, row in df.iterrows():
        scryfall_id = row['scryfall_id']
        
        # Skip rows with no scryfall_id
        if pd.isna(scryfall_id):
            skipped_count += 1
            continue

        card = db.query(Card).filter(Card.scryfall_id == scryfall_id).first()

        if card:
            # Update existing card
            card.quantity = row['quantity']
            card.condition = row['condition']
            updated_count += 1
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
            added_count += 1

    db.commit()
    
    return {"added": added_count, "updated": updated_count, "skipped": skipped_count}
