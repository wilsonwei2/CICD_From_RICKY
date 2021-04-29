import os
import json
from .shopify.shopify import ShopifyConnector
from .newstore.newstore import NewStoreConnector
from param_store.client import ParamStore

NS_HANDLER = None
SF_HANDLER = None
PARAM_STORE = None
SHOPIFY_CONFIG = {}
NEWSTORE_CONFIG = None
TENANT = os.environ.get('TENANT', 'goorin-brothers')
STAGE = os.environ.get('STAGE', 'x')

def _get_param_store():
    global PARAM_STORE # pylint: disable=global-statement
    if not PARAM_STORE:
        PARAM_STORE = ParamStore(TENANT, STAGE)

    return PARAM_STORE


def get_all_shopify_handlers():
    shopify_configs = _get_param_store().get_param('shopify')
    return _create_shopify_handlers([shopify_configs])

def get_shopify_config():
    global SHOPIFY_CONFIG # pylint: disable=global-statement
    if not SHOPIFY_CONFIG:
        param_store = _get_param_store()
        SHOPIFY_CONFIG = json.loads(param_store.get_param('shopify'))
    return SHOPIFY_CONFIG

def get_shopify_handler():
    global SF_HANDLER # pylint: disable=global-statement
    if not SF_HANDLER:
        shopify_config = get_shopify_config()
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
        config = json.loads(conf)
        config['channel'] = "USC"
        shopify_handler = ShopifyConnector(
            api_key=config['username'],
            password=config['password'],
            shop=config['shop']
        )
        handlers.append({
            'handler': shopify_handler,
            'config': config
        })

    return handlers


def _get_newstore_config():
    global NEWSTORE_CONFIG # pylint: disable=global-statement
    if not NEWSTORE_CONFIG:
        param_store = _get_param_store()
        NEWSTORE_CONFIG = json.loads(param_store.get_param('newstore'))

    return NEWSTORE_CONFIG


def get_newstore_handler():
    global NS_HANDLER # pylint: disable=global-statement
    if not NS_HANDLER:
        newstore_config = _get_newstore_config()
        NS_HANDLER = NewStoreConnector(
            host=newstore_config['host'],
            username=newstore_config['username'],
            password=newstore_config['password'],
        )
    return NS_HANDLER
