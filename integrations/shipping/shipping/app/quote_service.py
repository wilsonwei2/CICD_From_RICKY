import logging
from datetime import timedelta
from uuid import uuid4

from dateutil import parser

LOGGER = logging.getLogger(__name__)

def get_shipping_offer_response(delivery_country_code: str, service_level: str, provider_rate: str,
                                ready_by: str) -> {}:
    ready_by = parser.parse(ready_by)
    starts_at = ready_by + timedelta(days=3)
    ends_at = ready_by + timedelta(days=7)

    currency = "SEK" if delivery_country_code == "SE" else "EUR"

    return [{
        "offer": str(uuid4()),
        "provider_rate": provider_rate,
        "service_level": service_level,
        "delivery_estimate": {
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "expires_at": ends_at.isoformat()
        },
        "quote": {
            "price": 0,
            "currency": currency
        }
    }]
