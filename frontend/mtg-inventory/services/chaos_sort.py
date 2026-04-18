"""
Chaos Sort Service - Randomizes inventory ordering
"""
import random
import logging
from typing import List
from models import Card
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


class ChaosSort:
    """
    Service for applying chaos (random) sorting to inventory.
    
    Useful for:
    - Randomizing picking order to reduce bias
    - Shuffling storage locations
    - Load testing with large datasets
    - Preventing predictable patterns
    """
    
    def __init__(self, db: Session):
        """
        Initialize ChaosSort service
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def sort_inventory(self) -> List[str]:
        """
        Get all cards in chaotic (random) order.
        
        Returns:
            List of scryfall_ids in random order
        """
        # Fetch all cards
        cards = self.db.query(Card).all()
        
        # Extract scryfall_ids
        card_ids = [card.scryfall_id for card in cards]
        
        # Shuffle in-place
        random.shuffle(card_ids)
        
        return card_ids
    
    def sort_inventory_preserve_boxes(self) -> List[str]:
        """
        Sort inventory chaotically while keeping cards from same box together.
        
        This preserves physical organization while randomizing picking order.
        
        Returns:
            List of scryfall_ids preserving box groupings
        """
        cards = self.db.query(Card).all()
        
        # Group by box
        box_groups = {}
        for card in cards:
            box_num = card.box_number or 0
            if box_num not in box_groups:
                box_groups[box_num] = []
            box_groups[box_num].append(card.scryfall_id)
        
        # Shuffle each box internally
        for box_ids in box_groups.values():
            random.shuffle(box_ids)
        
        # Randomize box order
        box_numbers = list(box_groups.keys())
        random.shuffle(box_numbers)
        
        # Flatten to single list
        result = []
        for box_num in box_numbers:
            result.extend(box_groups[box_num])
        
        return result
    
    def sort_with_location_update(self):
        """
        Apply chaos sort and update location codes accordingly.
        
        Returns:
            List of updated Card objects with new location codes
        """
        # Get all cards in chaos order
        cards = self.db.query(Card).all()
        random.shuffle(cards)
        
        # Assign new locations
        from services.location_engine import assign_location
        
        try:
            for card in cards:
                # Clear old location
                card.location_code = None
                card.box_number = None
                card.slot_number = None

                # Assign new location
                assign_location(self.db, card)

            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Chaos location update failed; transaction rolled back")
            raise
        return cards
    
    def weighted_chaos_sort(self, weights: dict = None) -> List[str]:
        """
        Sort with weighted randomization (cards with certain properties prioritized).
        
        Example: foil cards get picked up more often
        
        Args:
            weights: Dict with card properties and their weight multipliers
            
        Returns:
            List of scryfall_ids with weighted randomization
        """
        cards = self.db.query(Card).all()
        
        if weights is None:
            weights = {
                'foil': 2.0,       # Foil cards appear more often
                'rare': 1.5,       # Rare cards appear more often
                'mint': 1.2        # Mint condition more often
            }
        
        # Build weights aligned with card IDs for weighted random sampling.
        card_ids = []
        card_weights = []
        for card in cards:
            weight = 1.0
            
            if card.foil and 'foil' in weights:
                weight *= weights['foil']
            
            if card.rarity == 'rare' and 'rare' in weights:
                weight *= weights['rare']
            
            if card.condition == 'mint' and 'mint' in weights:
                weight *= weights['mint']

            card_ids.append(card.scryfall_id)
            card_weights.append(weight)

        return random.choices(card_ids, weights=card_weights, k=len(cards))
    
    def chaos_sort_by_set(self) -> List[str]:
        """
        Sort chaotically but group by set.
        
        Useful for: organizing by edition while randomizing within editions
        
        Returns:
            List of scryfall_ids grouped by set then randomized
        """
        cards = self.db.query(Card).all()
        
        # Group by set
        set_groups = {}
        for card in cards:
            set_code = card.set_code or 'UNKNOWN'
            if set_code not in set_groups:
                set_groups[set_code] = []
            set_groups[set_code].append(card.scryfall_id)
        
        # Shuffle each set group
        for card_ids in set_groups.values():
            random.shuffle(card_ids)
        
        # Shuffle set order
        set_codes = list(set_groups.keys())
        random.shuffle(set_codes)
        
        # Flatten
        result = []
        for set_code in set_codes:
            result.extend(set_groups[set_code])
        
        return result
