import os
from .shopify.shopify import ShopifyConnector
from newstore_adapter.connector import NewStoreConnector
from pom_common.shopify import ShopManager

NS_HANDLER = None
SF_HANDLER = None
SHOPIFY_CONFIG = {}
NEWSTORE_CONFIG = None

TENANT = os.environ.get('TENANT', 'frankandoak')
STAGE = os.environ.get('STAGE', 'x')
REGION = os.environ.get('REGION', 'us-east-1')
CHANNEL = os.environ.get('warehouse_usc', 'MTLDC1')


def get_all_shopify_handlers():
    shop_manager = ShopManager(TENANT, STAGE, REGION)
    shopify_configs = [{
        'config': shop_manager.get_shop_config(shop_id),
        'shop_id': shop_id
    } for shop_id in shop_manager.get_shop_ids()]
    return _create_shopify_handlers(shopify_configs)

def get_shop_id(shop_name):
    get_all_shopify_handlers()
    for current in get_all_shopify_handlers():
        if current['config']['shop'] == shop_name:
            return current['shop_id']
    return None

def get_shopify_config(shop_id):
    global SHOPIFY_CONFIG # pylint: disable=global-statement
    if not SHOPIFY_CONFIG:
        shop_manager = ShopManager(TENANT, STAGE, REGION)
        SHOPIFY_CONFIG = shop_manager.get_shop_config(shop_id)
    return SHOPIFY_CONFIG

def get_shopify_handler(shop_id):
    global SF_HANDLER # pylint: disable=global-statement
    if not SF_HANDLER:
        shopify_config = get_shopify_config(shop_id)
        SF_HANDLER = ShopifyConnector(
            api_key=shopify_config['username'],
            password=shopify_config['password'],
            shop=shopify_config['shop']
        )
    return SF_HANDLER

def _create_shopify_handlers(configs):
    """Take an list of configs in the following format and return a list of
    shopify handler instances using them.

    Example `configs` element:
    [
        {
            "username": "12345",
            "password": "xxxxx",
            "secret": "my-secret",
            "shop": "my-shop",
            "host": "my-shop.myshopify.com"
        }
    ]

    Args:
        configs: A list of shopify configs.

    Returns:
        list:
            dict:
                handler: A specific shopify handler.
                config: The config details that correspond with the above handler.
    """
    handlers = []

    for conf in configs:
        config = conf['config']
        config['channel'] = CHANNEL
        shopify_handler = ShopifyConnector(
            api_key=config['username'],
            password=config['password'],
            shop=config['shop']
        )
        handlers.append({
            'handler': shopify_handler,
            'config': config,
            'shop_id': conf['shop_id']
        })

    return handlers


def get_newstore_handler(context):
    global NS_HANDLER # pylint: disable=global-statement
    if not NS_HANDLER:
        NS_HANDLER = NewStoreConnector(TENANT, context, raise_errors=True)
    return NS_HANDLER
