import json
import os
import logging

from shopify_payment_adaptor.handlers.shopify_handler import ShopifyConnector
from shopify_payment_adaptor.handlers.ns_handler import NShandler
from param_store.client import ParamStore

TENANT = os.environ.get('TENANT', 'frankandoak')
STAGE = os.environ.get('STAGE', 'x')

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

PARAM_STORE = None
SHOPIFY_HANDLER = {}
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
            host=newstore_config['NS_URL_API'],
            username=newstore_config['NS_USERNAME'],
            password=newstore_config['NS_PASSWORD']
        )
    return NEWSTORE_HANDLER


def get_shopify_handler():
    LOGGER.info(f'Getting Shopify info')

    global SHOPIFY_HANDLER
    if not SHOPIFY_HANDLER:
        handler_info = get_parameter_store().get_param('shopify')
        shopify_config = json.loads(handler_info)
        SHOPIFY_HANDLER = ShopifyConnector(
            api_key=shopify_config['username'],
            password=shopify_config['password'],
            shop=shopify_config['shop']
        )

    return SHOPIFY_HANDLER
