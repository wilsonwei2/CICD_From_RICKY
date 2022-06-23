"""
Client declaration to call Yotpo loyalty API.
"""

class YotpoLoyaltyService:
    """
    This is the main calling class for the Yotpo Loyalty API.
    """

    def __init__(self, guid: str, api_key: str):
        """
        Initialize the Yotpo Loyalty API.
        """
        self.guid = guid
        self.api_key = api_key
        self.auth_headers = {
            'x-api-key': self.api_key,
            'x-guid': self.guid,
            'Content-Type': 'application/json'
        }

    def create_order(self, order_payload: dict):
        pass
