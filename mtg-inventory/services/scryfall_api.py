"""
Service implementations for third-party API integrations
"""
import requests
from config import Config
from typing import Dict, Optional, List
import json

class ScryfallAPI:
    """Scryfall API client for MTG card data"""
    
    BASE_URL = "https://api.scryfall.com"
    
    @staticmethod
    def get_card_by_id(scryfall_id: str) -> Optional[Dict]:
        """
        Fetch card details from Scryfall by ID
        
        Returns:
            Dict with card data including prices, or None if not found
        """
        try:
            url = f"{ScryfallAPI.BASE_URL}/cards/{scryfall_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, ValueError, json.JSONDecodeError):
            return None
    
    @staticmethod
    def search_cards(query: str, limit: int = 10) -> List[Dict]:
        """Search for cards by query string"""
        try:
            url = f"{ScryfallAPI.BASE_URL}/cards/search"
            params = {"q": query, "unique": "cards"}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])[:limit]
        except (requests.exceptions.RequestException, ValueError, json.JSONDecodeError):
            return []



class eBayAPI:
    """eBay API client for listing creation and management"""
    
    BASE_URL = "https://api.ebay.com" if not Config.EBAY_SANDBOX_MODE else "https://api.sandbox.ebay.com"
    
    def __init__(self):
        self.client_id = Config.EBAY_CLIENT_ID
        self.client_secret = Config.EBAY_CLIENT_SECRET
        self.refresh_token = Config.EBAY_REFRESH_TOKEN
        self._access_token = None
    
    def get_access_token(self) -> Optional[str]:
        """Get OAuth access token from eBay"""
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            return None
        
        try:
            import base64
            url = f"{self.BASE_URL}/identity/v1/oauth2/token"
            credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            headers = {
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token
            }
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            self._access_token = result.get("access_token")
            return self._access_token
        except (requests.exceptions.RequestException, ValueError, json.JSONDecodeError):
            pass
        return None
    
    def create_listing(self, listing_data: Dict) -> Optional[str]:
        """
        Create an item listing on eBay
        
        Args:
            listing_data: Dict with listing details (title, description, price, etc.)
        
        Returns:
            Listing ID if successful, None otherwise
        """
        if not self._access_token:
            self.get_access_token()
        if not self._access_token:
            return None
        
        try:
            url = f"{self.BASE_URL}/sell/inventory/v1/inventory_item"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json"
            }
            response = requests.post(url, headers=headers, json=listing_data, timeout=10)
            response.raise_for_status()
            # eBay returns location header with the item ID
            location = response.headers.get("Location", "")
            if location:
                return location.split("/")[-1]
        except requests.exceptions.RequestException:
            pass
        return None
    
    def publish_listing(self, listing_id: str) -> bool:
        """Publish a draft listing"""
        if not self._access_token:
            self.get_access_token()
        if not self._access_token:
            return False
        
        try:
            url = f"{self.BASE_URL}/sell/inventory/v1/inventory_item/{listing_id}/publish_variation"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json"
            }
            response = requests.post(url, headers=headers, timeout=10)
            return response.status_code in [200, 204]
        except requests.exceptions.RequestException:
            pass
        return False

    def update_listing(self, listing_id: str, update_data: Dict) -> Optional[Dict]:
        """Update an existing eBay inventory listing."""
        if not self._access_token:
            self.get_access_token()
        if not self._access_token:
            return None

        try:
            url = f"{self.BASE_URL}/sell/inventory/v1/inventory_item/{listing_id}"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }
            response = requests.put(url, headers=headers, json=update_data, timeout=10)
            if response.status_code in (200, 204):
                return {"success": True, "listing_id": listing_id}

            try:
                return response.json()
            except Exception:
                return {"success": False, "status_code": response.status_code}
        except requests.exceptions.RequestException:
            return None
