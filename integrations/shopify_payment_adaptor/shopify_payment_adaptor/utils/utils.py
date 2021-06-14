import json
import os
import logging

from shopify_payment_adaptor.handlers.shopify_handler import ShopifyConnector
from shopify_payment_adaptor.handlers.ns_handler import NShandler
from param_store.client import ParamStore
from pom_common.shopify import ShopManager

TENANT = os.environ.get('TENANT', 'frankandoak')
STAGE = os.environ.get('STAGE', 'x')
REGION = os.environ.get('REGION', 'us-east-1')

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

PARAM_STORE = None
SHOPIFY_HANDLERS = {}
NEWSTORE_HANDLER = None

TRUE_VALUES = ['true', '1', 't']
ERRORS_TO_RETRY = [
    'Too Many Requests', # Got from Shopify API documentation
    'Internal Server Error', # Got from Shopify API documentation
    'Gateway Timeout', # Got from Shopify API documentation
    'Exceeded 8 calls per second for api client', # Got from actual call to Shopify, from AWS logs
    'Reduce request rates to resume uninterrupted service' # Got from actual call to Shopify, from AWS logs
]


def is_capture_credit_card(payment_method: str) -> bool:
    return payment_method != 'gift_card'


def is_capture_gift_card(payment_method: str) -> bool:
    return payment_method == 'gift_card'


async def create_fullfillment(shopify_conector, shopify_order_id, line_items, tracking_number):
    line_items = [{'id': item['id']}
                  for item in line_items]
    data_fullfil = {
        'fulfillment': {
            'tracking_number': tracking_number,
            'notify_customer': True,
            'line_items': line_items
        }
    }
    fullfilment_rsp = await shopify_conector.create_fulfillment(
        order_id=shopify_order_id,
        data=data_fullfil
    )
    return fullfilment_rsp


def get_parameter_store(tenant: str = TENANT, stage: str = STAGE):
    global PARAM_STORE
    if not PARAM_STORE:
        PARAM_STORE = ParamStore(tenant, stage)
    return PARAM_STORE


def get_newstore_handler():
    global NEWSTORE_HANDLER
    if not NEWSTORE_HANDLER:
        newstore_config = json.loads(
            get_parameter_store().get_param('newstore'))
        NEWSTORE_HANDLER = NShandler(
            host=newstore_config['host'],
            username=newstore_config['username'],
            password=newstore_config['password']
        )
    return NEWSTORE_HANDLER


def get_shopify_handlers():
    global SHOPIFY_HANDLERS
    if len(SHOPIFY_HANDLERS) == 0:
        shop_manager = ShopManager(TENANT, STAGE, REGION)

        for shop_id in shop_manager.get_shop_ids():
            shopify_config = shop_manager.get_shop_config(shop_id)
            currency = shopify_config['currency']

            SHOPIFY_HANDLERS[currency] = ShopifyConnector(
                api_key=shopify_config['username'],
                password=shopify_config['password'],
                shop=shopify_config['shop']
            )

    return SHOPIFY_HANDLERS.values()


def get_shopify_handler(currency):
    if len(SHOPIFY_HANDLERS) == 0:
        get_shopify_handlers()

    return SHOPIFY_HANDLERS[currency]
