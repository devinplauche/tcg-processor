from models import Box
from config import Config

def assign_location(db, card):
    box_capacity = Config.BOX_CAPACITY
    
    # Find the current or create a new box
    current_box = db.query(Box).filter(Box.current_count < box_capacity).order_by(Box.box_number).first()
    
    if not current_box:
        # Get the last box number to determine the new box number
        last_box = db.query(Box).order_by(Box.box_number.desc()).first()
        new_box_number = (last_box.box_number + 1) if last_box else 1
        current_box = Box(box_number=new_box_number, capacity=box_capacity, current_count=0)
        db.add(current_box)
        db.flush() # To get the box_number

    # Assign the next available slot
    slot_number = current_box.current_count + 1
    card.box_number = current_box.box_number
    card.slot_number = slot_number
    card.location_code = f"BOX-{current_box.box_number:04d}-SLOT-{slot_number:04d}"
    
    current_box.current_count += 1
    db.flush()  # Flush so the next query sees the updated current_count
