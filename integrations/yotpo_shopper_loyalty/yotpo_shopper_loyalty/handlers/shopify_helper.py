import logging
from yotpo_shopper_loyalty.handlers.utils import Utils

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
SHOPIFY_SERVICE_LEVEL_MAP_CONFIG = Utils.get_instance().get_shopify_service_level_map()


## Get the order risks from shopify.
def get_order_risks(order_id, shop_id):
    shopify_connector = Utils.get_instance().get_shopify_handler(shop_id)
    return shopify_connector.get_order_risks(order_id)


def get_shipment_service_level(code='', title='', country_code=''):
    country_code = country_code.upper()
    LOGGER.info(f'Code: {code}; Title: {title}, Country code: {country_code}')

    if not country_code in SHOPIFY_SERVICE_LEVEL_MAP_CONFIG:
        country_code = 'INT'

    country_service_levels = SHOPIFY_SERVICE_LEVEL_MAP_CONFIG[country_code]

    for shipping_option_key in country_service_levels.keys():
        if (code and code.startswith(shipping_option_key.lower())) \
                or (title and title.startswith(shipping_option_key.lower())):
            return country_service_levels[shipping_option_key]

    return country_service_levels['default']
