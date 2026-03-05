"""
API Contract Definitions - Schemas that services must conform to

These contracts define the expected structure, fields, and types that external
APIs should return. Used for contract testing to ensure services stay in sync
with API changes.
"""

from typing import Dict, Any, List, Type


class APIContract:
    """Base class for API contracts"""
    
    required_fields: List[str] = []
    optional_fields: List[str] = []
    field_types: Dict[str, Type] = {}
    
    @classmethod
    def validate(cls, response: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate a response against this contract
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        # Check required fields
        for field in cls.required_fields:
            if field not in response:
                errors.append(f"Missing required field: {field}")
        
        # Check types
        for field, expected_type in cls.field_types.items():
            if field in response and response[field] is not None:
                if not isinstance(response[field], expected_type):
                    actual_type = type(response[field]).__name__
                    expected = expected_type.__name__
                    errors.append(
                        f"Field '{field}' has wrong type: "
                        f"expected {expected}, got {actual_type}"
                    )
        
        return len(errors) == 0, errors


class ScryfallCardContract(APIContract):
    """Contract for Scryfall card lookup response"""
    
    required_fields = ["id", "name", "type_line"]
    optional_fields = ["prices", "image_uris", "oracle_text", "mana_cost"]
    
    field_types = {
        "id": str,
        "name": str,
        "type_line": str,
        "prices": dict,
        "image_uris": dict,
        "oracle_text": str,
        "mana_cost": str,
    }


class ScryfallSearchContract(APIContract):
    """Contract for Scryfall search response"""
    
    required_fields = ["data"]
    optional_fields = ["has_more", "next_page"]
    
    field_types = {
        "data": list,
        "has_more": bool,
    }


class TCGPlayerAuthContract(APIContract):
    """Contract for TCGPlayer authentication response"""
    
    required_fields = ["success", "data"]
    optional_fields = []
    
    field_types = {
        "success": bool,
        "data": dict,
    }


class TCGPlayerTokenContract(APIContract):
    """Contract for TCGPlayer token data"""
    
    required_fields = ["token"]
    optional_fields = ["user_id", "user_email"]
    
    field_types = {
        "token": str,
    }


class TCGPlayerPricingContract(APIContract):
    """Contract for TCGPlayer pricing response"""
    
    required_fields = ["success", "data"]
    optional_fields = []
    
    field_types = {
        "success": bool,
        "data": dict,
    }


class TCGPlayerPricingDataContract(APIContract):
    """Contract for TCGPlayer pricing data"""
    
    required_fields = ["productId", "lowestListing"]
    optional_fields = ["lowestListingFoil", "average", "averageFoil"]
    
    field_types = {
        "productId": int,
        "lowestListing": dict,
        "lowestListingFoil": dict,
        "average": (int, float),
    }


class eBayAccessTokenContract(APIContract):
    """Contract for eBay OAuth access token response"""
    
    required_fields = ["access_token", "token_type", "expires_in"]
    optional_fields = []
    
    field_types = {
        "access_token": str,
        "token_type": str,
        "expires_in": int,
    }


class eBayListingContract(APIContract):
    """Contract for eBay draft listing response"""
    
    required_fields = ["itemId"]
    optional_fields = ["title", "price", "status"]
    
    field_types = {
        "itemId": str,
        "title": str,
        "price": (int, float),
    }


class GoogleDriveFileContract(APIContract):
    """Contract for Google Drive file metadata"""
    
    required_fields = ["id", "name", "mimeType"]
    optional_fields = ["webViewLink", "modifiedTime"]
    
    field_types = {
        "id": str,
        "name": str,
        "mimeType": str,
        "webViewLink": str,
        "modifiedTime": str,
    }


# Helpful union type for testing
API_CONTRACTS = {
    'scryfall_card': ScryfallCardContract,
    'scryfall_search': ScryfallSearchContract,
    'tcgplayer_auth': TCGPlayerAuthContract,
    'tcgplayer_token': TCGPlayerTokenContract,
    'tcgplayer_pricing': TCGPlayerPricingContract,
    'tcgplayer_pricing_data': TCGPlayerPricingDataContract,
    'ebay_token': eBayAccessTokenContract,
    'ebay_listing': eBayListingContract,
    'google_drive_file': GoogleDriveFileContract,
}
