from unittest.mock import patch


def setup_patches(test_self):
    patcher_locations = patch('netsuite_returns_injection.helpers.utils.Utils.get_netsuite_location_map')
    test_self.patched_locations = patcher_locations.start()
    test_self.patched_locations.return_value = NEWSTORE_TO_NETSUITE_LOCATIONS

    patcher_payment_items = patch('netsuite_returns_injection.helpers.utils.Utils.get_nws_to_netsuite_payment')
    test_self.patched_payment_items = patcher_payment_items.start()
    test_self.patched_payment_items.return_value = NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS

    patcher_giftcard_product_ids = patch('netsuite_returns_injection.helpers.utils.Utils._get_giftcard_product_ids')
    test_self.patched_giftcard_product_ids = patcher_giftcard_product_ids.start()
    test_self.patched_giftcard_product_ids.return_value = NEWSTORE_GIFTCARD_PRODUCT_IDS

    patcher_timezone_mapping = patch('netsuite_returns_injection.helpers.utils.Utils.get_dc_timezone_mapping_config')
    test_self.patched_timezone_mapping = patcher_timezone_mapping.start()
    test_self.patched_timezone_mapping.return_value = DC_TIMEZONE_MAPPING

    patcher_channels = patch('netsuite_returns_injection.helpers.utils.Utils.get_nws_to_netsuite_channel')
    test_self.patched_channels = patcher_channels.start()
    test_self.patched_channels.return_value = NEWSTORE_TO_NETSUITE_CHANNEL


# May be good to add in which use Pixior vs Bleckman for fulfillment purposes
# KEY: https://github.com/NewStore/newstore-integrations/blob/master/tenants/aninebing/bootstrap/stores.yaml
# ID: https://4674622-sb1.app.netsuite.com/app/common/otherlists/locationlist.nl?whence=
# SELLING_ID (CSEG_AB_SELLINGLOC): https://4674622-sb1.app.netsuite.com/app/common/custom/custrecordentrylist.nl?rectype=275


NEWSTORE_TO_NETSUITE_LOCATIONS = {
    "001": {
        "id": 5,
        "selling_id": 7,
        "name": "001_LA_WeHo",
        "email": "flagshipla@aninebing.com",
        "id_damage": "123",
        "subsidiary_id": 1
    },
    "002": {
        "id": 6,
        "selling_id": 9,
        "name": "002_NY_WVillage",
        "email": "aninebingstorenyc@aninebing.com",
        "id_damage": "124",
        "subsidiary_id": 1
    },
    "003": {
        "id": 12,
        "selling_id": 4,
        "name": "003_PA_3Arr",
        "email": "aninebingstoreparis@aninebing.com",
        "id_damage": "122",
        "subsidiary_id": 1
    },
    "004": {
        "id": 10,
        "selling_id": 5,
        "name": "004_LN_Harvey_Nichols",
        "email": "managerlondon@aninebing.com",
        "id_damage": "118",
        "subsidiary_id": 1
    },
    "005": {
        "id": 15,
        "selling_id": 1,
        "name": "005_BA_Eixample",
        "email": "aninebingstorebarcelona@aninebing.com",
        "id_damage": "119",
        "subsidiary_id": 1
    },
    "006": {
        "id": 13,
        "selling_id": 2,
        "name": "006_BE_Mitte",
        "email": "aninebingstoreberlin@aninebing.com",
        "id_damage": "120",
        "subsidiary_id": 1
    },
    "007": {
        "id": 14,
        "selling_id": 3,
        "name": "007_MD_Salamanca",
        "email": "aninebingstoremadrid@aninebing.com",
        "id_damage": "121",
        "subsidiary_id": 1
    },
    "008": {
        "id": 7,
        "selling_id": 10,
        "name": "008_NY_SoHo",
        "email": "aninebingstoresoho@aninebing.com",
        "id_damage": "125",
        "subsidiary_id": 1
    },
    "009": {
        "id": 8,
        "selling_id": 8,
        "name": "009_LA_Pacific_Palisades",
        "email": "aninebingstorepalisades@aninebing.com",
        "id_damage": "219",
        "subsidiary_id": 1
    },
    "010": {
        "id": 116,
        "selling_id": 6,
        "name": "010_LN_Mayfair",
        "email": "aninebingstoremayfair@aninebing.com",
        "id_damage": "218",
        "subsidiary_id": 3
    },
    "011": {
        "id": 226,
        "selling_id": 103,
        "name": "011_NY_Madison",
        "email": "aninebingstoremadison@aninebing.com",
        "id_damage": "227",
        "subsidiary_id": 1
    },
    "DEFAULT": {
        "id": 0,
        "selling_id": 0,
        "name": "Default",
        "email": "default@aninebing.com",
        "id_damage": "",
        "subsidiary_id": 1
    }
}

# Search for items of type Payment: https://4674622-sb1.app.netsuite.com/app/common/item/itemlist.nl?whence=
NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS = {
    "cash": 8282,
    "credit_card": {
        "adyen": 572,
        "shopify": 9204,
        "stripe": 572,
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
