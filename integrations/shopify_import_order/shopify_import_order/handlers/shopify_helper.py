import logging
from shopify_import_order.handlers.utils import Utils

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
SHOPIFY_SERVICE_LEVEL_MAP_CONFIG = Utils.get_instance().get_shopify_service_level_map()


## Get the order risks from shopify.
def get_order_risks(order_id, shop_id):
    shopify_connector = Utils.get_instance().get_shopify_handler(shop_id)
    return shopify_connector.get_order_risks(order_id)


def get_shipment_service_level(code, title):
    LOGGER.info(f'Code: {code}; Title: {title}')
    for shipping_option_key in SHOPIFY_SERVICE_LEVEL_MAP_CONFIG.keys():
        if (code and code.startswith(shipping_option_key.lower())) \
        		or (title and title.startswith(shipping_option_key.lower())):
            return SHOPIFY_SERVICE_LEVEL_MAP_CONFIG[shipping_option_key]

    return SHOPIFY_SERVICE_LEVEL_MAP_CONFIG['default']
