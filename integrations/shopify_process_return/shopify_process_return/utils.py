import os
import json
from .shopify.shopify import ShopifyConnector
from newstore_adapter.connector import NewStoreConnector
from pom_common.shopify import ShopManager
from param_store.client import ParamStore

NS_HANDLER = None
SF_HANDLERS = {}
SHOPIFY_CONFIGS = {}
NEWSTORE_CONFIG = None
PARAM_STORE = None
SHOPIFY_LOCATIONS_MAP = {}

TENANT = os.environ.get('TENANT', 'frankandoak')
STAGE = os.environ.get('STAGE', 'x')
REGION = os.environ.get('REGION', 'us-east-1')
CHANNEL = os.environ.get('warehouse_usc', 'MTLDC1')


def get_parameter_store(tenant=TENANT, stage=STAGE):
    global PARAM_STORE  # pylint: disable=global-statement
    if not PARAM_STORE:
        PARAM_STORE = ParamStore(tenant, stage)
    return PARAM_STORE


def get_shopify_locations_map():
    global SHOPIFY_LOCATIONS_MAP  # pylint: disable=global-statement
    if not SHOPIFY_LOCATIONS_MAP:
        SHOPIFY_LOCATIONS_MAP = json.loads(
            get_parameter_store().get_param('shopify/dc_location_id_map'))
    return SHOPIFY_LOCATIONS_MAP


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
    global SHOPIFY_CONFIGS  # pylint: disable=global-statement
    if not shop_id in SHOPIFY_CONFIGS:
        shop_manager = ShopManager(TENANT, STAGE, REGION)
        SHOPIFY_CONFIGS[shop_id] = shop_manager.get_shop_config(shop_id)
    return SHOPIFY_CONFIGS[shop_id]


def get_shopify_handler(shop_id):
    global SF_HANDLERS  # pylint: disable=global-statement
    if not shop_id in SF_HANDLERS:
        shopify_config = get_shopify_config(shop_id)
        SF_HANDLERS[shop_id] = ShopifyConnector(
            api_key=shopify_config['username'],
            password=shopify_config['password'],
            shop=shopify_config['shop']
        )
    return SF_HANDLERS[shop_id]


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
    global NS_HANDLER  # pylint: disable=global-statement
    if not NS_HANDLER:
        newstore_creds = json.loads(
            get_parameter_store().get_param('newstore'))
        NS_HANDLER = NewStoreConnector(tenant=newstore_creds['tenant'], context=context,
                                       username=newstore_creds['username'], password=newstore_creds['password'],
                                       host=newstore_creds['host'], raise_errors=True)
    return NS_HANDLER
