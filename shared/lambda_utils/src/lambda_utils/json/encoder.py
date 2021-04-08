"""
Custom JSON Encoder
"""
import json
from decimal import Decimal

class NewStoreJSONEncoder(json.JSONEncoder):
    """ A JSONEncoder that knows how to serialize Decimal"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)
