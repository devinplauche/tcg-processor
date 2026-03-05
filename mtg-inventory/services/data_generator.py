"""
Data Generator Service - Generate realistic MTG card data for testing

Supports generating large datasets (100k+ cards) efficiently using batching.
"""
import random
import uuid
from typing import List, Optional
from models import Card
from sqlalchemy.orm import Session


class DataGenerator:
    """
    Generate realistic MTG card data for testing and load testing.
    
    Can generate 100k+ cards efficiently using batch inserts.
    """
    
    # Realistic MTG data
    SETS = [
        'LEA', 'LEB', '2ED', '3ED', '4ED', '5ED', '6ED', '7ED', '8ED', '9ED', '10E',
        'M10', 'M11', 'M12', 'M13', 'M14', 'M15',
        'KTK', 'FRF', 'DTK',  # Khans block
        'ORI', 'BFZ', 'OGW',  # Origins block
        'SOI', 'EMN',  # Shadows block
        'KLD', 'AER',  # Kaladesh block
        'AKH', 'HOU',  # Amonkhet block
        'XLN', 'RIX',  # Ixalan block
        'DOM', 'M19',  # Core 2019
        'GRN', 'RNA', 'WAR',  # Ravnica Allegiance block
        'M20', 'ELD',  # Core 2020
        'THB', 'IKO',  # Theros/Ikoria
        'M21', 'ZNR',  # Core 2021 / Zendikar Rising
        'KHM', 'STX',  # Kaldheim / Strixhaven
        'AFR', 'MID', 'VOW',  # AFR through Vow of the Vampire
        'NEO', 'SNC', 'HBG',  # Recent sets
        'ONE', 'MOM', 'LCI',  # Latest sets
    ]
    
    CONDITIONS = ['mint', 'near_mint', 'lightly_played', 'moderately_played', 'heavily_played', 'damaged']
    
    COLORS = ['W', 'U', 'B', 'R', 'G', 'C', 'WU', 'WB', 'WR', 'WG', 'UB', 'UR', 'UG', 'BR', 'BG', 'RG']
    
    RARITIES = ['common', 'uncommon', 'rare', 'mythic']
    
    LANGUAGES = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ja', 'zh', 'ko', 'ru']
    
    CARD_NAMES = [
        'Ace of Archers', 'Archfiend of Depravity', 'Arid Mesa', 'Ash Barrens',
        'Awakening Zone', 'Azusa Lost but Seeking', 'Bad River', 'Badlands',
        'Balloon Peddler', 'Bamboo Grove', 'Bandit Queen', 'Banishing Light',
        'Bare Root', 'Barkhide Troll', 'Barrage Ogre', 'Basilica Heliod',
        'Bathhouse Flayer', 'Battle Screech', 'Bayou', 'Beach Paladin',
        'Beaker Pusher', 'Bearscape', 'Beasts Embrace', 'Bedeck',
        'Bedevil', 'Bedlam Reveler', 'Beggars Decree', 'Behalf of Behemoth', 'Behold',
        'Belcher', 'Belief', 'Belligerent Whiptail', 'Bells of Lost Souls',
        'Belonging', 'Below the Surface', 'Belt Collector', 'Bemoan', 'Bend of Fate',
    ]
    
    def __init__(self, db: Session):
        """
        Initialize DataGenerator
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def generate(self, count: int = 1000, batch_size: int = 500) -> int:
        """
        Generate realistic MTG card data.
        
        Uses batch inserts for efficiency with large datasets.
        
        Args:
            count: Number of cards to generate (default 1000)
            batch_size: Number of cards per batch insert (default 500)
            
        Returns:
            Total number of cards generated
        """
        generated = 0
        batch = []
        
        for i in range(count):
            card = Card(
                scryfall_id=self._generate_scryfall_id(),
                manabox_id=self._generate_manabox_id(),
                name=self._generate_card_name(i),
                set_code=random.choice(self.SETS),
                set_name=self._get_set_name(),
                collector_number=str(random.randint(1, 300)),
                foil=random.random() < 0.15,  # 15% foil
                rarity=random.choice(self.RARITIES),
                quantity=random.randint(1, 4),
                condition=random.choice(self.CONDITIONS),
                language=random.choice(self.LANGUAGES),
                purchase_price=round(random.uniform(0.25, 500.0), 2),
            )
            batch.append(card)
            
            # Batch insert
            if len(batch) >= batch_size:
                self.db.add_all(batch)
                self.db.commit()
                generated += len(batch)
                batch = []
                print(f"Generated {generated} cards...")
            
            # Progress indicator every 5k cards
            if generated % 5000 == 0 and generated > 0:
                print(f"Progress: {generated}/{count} cards ({100*generated/count:.1f}%)")
        
        # Insert remaining
        if batch:
            self.db.add_all(batch)
            self.db.commit()
            generated += len(batch)
        
        return generated
    
    def _generate_scryfall_id(self) -> str:
        """Generate a unique Scryfall ID (UUID format)"""
        return str(uuid.uuid4())
    
    def _generate_manabox_id(self) -> str:
        """Generate a ManaBox ID"""
        return str(random.randint(10000, 99999))
    
    def _generate_card_name(self, index: int) -> str:
        """Generate a card name (mix of real and generated)"""
        if index < len(self.CARD_NAMES):
            return self.CARD_NAMES[index % len(self.CARD_NAMES)]
        
        # Generate synthetic names
        prefixes = ['Ancient', 'Dark', 'Mighty', 'Cursed', 'Blessed', 'Ethereal', 'Zombie', 'Shadow']
        suffixes = ['Troll', 'Knight', 'Mage', 'Beast', 'Demon', 'Angel', 'Dragon', 'Spirit']
        
        return f"{random.choice(prefixes)} {random.choice(suffixes)} #{index}"
    
    def _get_set_name(self) -> str:
        """Get full set name from set code"""
        set_names = {
            'LEA': 'Limited Edition Alpha', 'LEB': 'Limited Edition Beta',
            '2ED': 'Unlimited', '3ED': 'Revised', '4ED': 'Fourth Edition',
            '5ED': 'Fifth Edition', '6ED': 'Sixth Edition',
            'M10': 'Magic 2010', 'M11': 'Magic 2011', 'M12': 'Magic 2012',
            'KTK': 'Khans of Tarkir', 'FRF': 'Fate Reforged',
            'ORI': 'Magic Origins', 'BFZ': 'Battle for Zendikar',
            'SOI': 'Shadows over Innistrad', 'KLD': 'Kaladesh',
            'EMN': 'Eldritch Moon', 'AER': 'Aether Revolt',
            'AKH': 'Amonkhet', 'HOU': 'Hour of Devastation',
            'XLN': 'Ixalan', 'RIX': 'Rivals of Ixalan',
            'DOM': 'Dominaria', 'M19': 'Core Set 2019',
            'GRN': 'Guilds of Ravnica', 'RNA': 'Ravnica Allegiance',
            'WAR': 'War of the Spark', 'M20': 'Core Set 2020',
            'ELD': 'Throne of Eldraine', 'THB': 'Theros Beyond Death',
            'IKO': 'Ikoria: Lair of Behemoths', 'M21': 'Core Set 2021',
            'ZNR': 'Zendikar Rising', 'KHM': 'Kaldheim',
            'STX': 'Strixhaven: School of Mages', 'AFR': 'Adventures in the Forgotten Realms',
            'MID': 'Innistrad: Midnight Hunt', 'VOW': 'Innistrad: Crimson Vow',
            'NEO': 'Kamigawa: Neon Dynasty', 'SNC': 'Streets of New Capenna',
            'HBG': 'Homelands', 'ONE': 'ONE', 'MOM': 'March of the Machine',
            'LCI': 'Lost Caverns of Ixalan',
        }
        return set_names.get(random.choice(self.SETS), 'Unknown Set')
    
    def generate_sparse(self, count: int = 10000, rarity_distribution: dict = None) -> int:
        """
        Generate cards with specific rarity distribution.
        
        Useful for realistic inventory simulation.
        
        Args:
            count: Total cards to generate
            rarity_distribution: Dict with rarity percentages
                {'common': 0.6, 'uncommon': 0.25, 'rare': 0.13, 'mythic': 0.02}
                
        Returns:
            Total generated
        """
        if rarity_distribution is None:
            rarity_distribution = {
                'common': 0.55,
                'uncommon': 0.3,
                'rare': 0.13,
                'mythic': 0.02
            }
        
        batch = []
        batch_size = 1000
        
        for i in range(count):
            # Choose rarity based on distribution
            rarity = random.choices(
                list(rarity_distribution.keys()),
                weights=list(rarity_distribution.values())
            )[0]
            
            card = Card(
                scryfall_id=self._generate_scryfall_id(),
                manabox_id=self._generate_manabox_id(),
                name=self._generate_card_name(i),
                set_code=random.choice(self.SETS),
                set_name=self._get_set_name(),
                collector_number=str(random.randint(1, 300)),
                foil=random.random() < (0.25 if rarity == 'mythic' else 0.15),
                rarity=rarity,
                quantity=random.randint(1, max(1, 5 - self.RARITIES.index(rarity))),
                condition=random.choice(self.CONDITIONS),
                language=random.choice(self.LANGUAGES),
                purchase_price=self._price_by_rarity(rarity),
            )
            batch.append(card)
            
            if len(batch) >= batch_size:
                self.db.add_all(batch)
                self.db.commit()
                batch = []
        
        if batch:
            self.db.add_all(batch)
            self.db.commit()
        
        return count
    
    def _price_by_rarity(self, rarity: str) -> float:
        """Generate realistic price based on rarity"""
        price_ranges = {
            'common': (0.01, 0.5),
            'uncommon': (0.05, 2.0),
            'rare': (0.5, 50.0),
            'mythic': (5.0, 500.0),
        }
        min_price, max_price = price_ranges.get(rarity, (0.1, 10.0))
        return round(random.uniform(min_price, max_price), 2)
