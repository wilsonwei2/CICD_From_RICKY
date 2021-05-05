from unittest.mock import patch
import os


def setup_patches(test_self):
    patcher_locations = patch('netsuite_item_fulfillment_injection.helpers.utils.Utils.get_netsuite_location_map')
    test_self.patched_locations = patcher_locations.start()
    test_self.patched_locations.return_value = NEWSTORE_TO_NETSUITE_LOCATIONS

NEWSTORE_TO_NETSUITE_LOCATIONS = {
    "DIXST": {
        "id": 11,
        "id_damage": 12,
        "selling_id": -1,
        "name": "DIXST - Dix30",
        "email": "dix30@frankandoak.com",
        "subsidiary_id": "1"
    },
    "DONST": {
        "id": 13,
        "id_damage": 14,
        "selling_id": -1,
        "name": "DONST - Don Mills",
        "email": "donmills@frankandoak.com",
        "subsidiary_id": "1"
    },
    "FOYST": {
        "id": 19,
        "id_damage": 20,
        "selling_id": -1,
        "name": "FOYST - Ste-Foy",
        "email": "sainte-foy@frankandoak.com",
        "subsidiary_id": "1"
    },
    "MTLST": {
        "id": 30,
        "id_damage": 31,
        "selling_id": -1,
        "name": "MTLST - Atelier Mile-End",
        "email": "atelier@frankandoak.com",
        "subsidiary_id": "1"
    },
    "RIDST": {
        "id": 36,
        "id_damage": 37,
        "selling_id": -1,
        "name": "RIDST - Rideau Center",
        "email": "rideau@frankandoak.com",
        "subsidiary_id": "1"
    },
    "STANST": {
        "id": 42,
        "id_damage": 43,
        "selling_id": -1,
        "name": "STANST - Stanley",
        "email": "stanley@frankandoak.com",
        "subsidiary_id": "1"
    },
    "STWST": {
        "id": 44,
        "id_damage": 45,
        "selling_id": -1,
        "name": "STWST - Stanley Women",
        "email": "stanleywomen@frankandoak.com",
        "subsidiary_id": "1"
    },
    "TECST": {
        "id": 46,
        "id_damage": 47,
        "selling_id": -1,
        "name": "TECST -Toronto Eaton Center",
        "email": "tec@frankandoak.com",
        "subsidiary_id": "1"
    },
    "TOST": {
        "id": 59,
        "id_damage": 63,
        "selling_id": -1,
        "name": "TOST - Queen West",
        "email": "toronto@frankandoak.com",
        "subsidiary_id": "1"
    },
    "VANST": {
        "id": 50,
        "id_damage": 51,
        "selling_id": -1,
        "name": "VANST - Cordova",
        "email": "vancouver@frankandoak.com",
        "subsidiary_id": "1"
    },
    "VIAST": {
        "id": 52,
        "id_damage": 53,
        "selling_id": -1,
        "name": "VIAST - Studio Mile-End",
        "email": "studio@frankandoak.com",
        "subsidiary_id": "1"
    },
    "MTLDC1": {
        "id": 7,
        "id_damage": 64,
        "selling_id": -1,
        "name": "Montreal DC",
        "email": "ops@frankandoak.com",
        "subsidiary_id": "1"
    }
}

# Search for items of type Payment: https://4674622-sb1.app.netsuite.com/app/common/item/itemlist.nl?whence=
NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS = {
    "cash": 8282,
    "credit_card": {
        "adyen": 572,
        "shopify": 9204
    },
    "gift_card": {
        "usd": 8229,
        "eur": 8230,
        "gbp": 8231,
    },
    "check": 8493,
    "eft": 8492,
    "store_credit": 8491,
    "lightspeed_order": 8489,
    "cod": 8490,
}

DC_TIMEZONE_MAPPING = {
    "Pixior Ecom": "America/Los_Angeles",
    "Bleckmann Ecom": "Europe/Brussels",
    "Pixior WSL": "America/Los_Angeles",
    "Bleckmann WSL": "Europe/Brussels",
    "Pixior WSL ASAP": "America/Los_Angeles",
    "Bleckmann WSL ASAP": "Europe/Brussels"
}

# Search items for "gift card", they will be of type non-inventory item:
#    https://4674622-sb1.app.netsuite.com/app/common/item/itemlist.nl?whence=
NEWSTORE_GIFTCARD_PRODUCT_IDS = [
    8232,  # US
    8233,  # EU
    8234,  # UK
]

# https://4674622-sb1.app.netsuite.com/app/common/custom/custrecordentrylist.nl?rectype=153
NEWSTORE_TO_NETSUITE_CHANNEL = {
    "web": 1,  # Online
    "store": 3,  # Retail Order
    "wholesale": 2,  # Wholesale
    "mobile": None
}

# https://4674622-sb1.app.netsuite.com/app/common/item/shipitems.nl
NEWSTORE_TO_NETSUITE_SHIPPING_METHODS = {
    "GROUND": 4,
    "2_DAY": 8256,
    "NEXT_DAY": 588,
    "UPS_STANDARD_INT": 8261,
    "UPS_WORLDWIDE_EXPEDITED": 8260,
    "UPS_WORLDWIDE_EXPRESS": 8258,
    "UPS_WORLDWIDE_SAVER": 8259,
    "DHL_WORLDWIDE_EXPRESS": 8255,
    "3RD_DAY_SELECT": 8257,
    "FEDEX_GROUND": 587,
    "IN_STORE_PICKUP": 589
}
