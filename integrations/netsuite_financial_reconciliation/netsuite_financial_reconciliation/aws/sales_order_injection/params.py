import json
import os

# Runs startup processes (expecting to be 'unused')
import netsuite.netsuite_environment_loader  # pylint: disable=W0611
from netsuite.service import CustomerCurrencyList, CustomerCurrency, RecordRef
from param_store.client import ParamStore

PARAM_STORE = None
NEWSTORE_CONFIG = None
NETSUITE_CONFIG = None
NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG = None
NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS_CONFIG = None
NEWSTORE_GIFTCARD_PRODUCT_IDS_CONFIG = None
DC_TIMEZONE_MAPPING_CONFIG = None
NEWSTORE_TO_NETSUITE_CHANNEL_CONFIG = None
NEWSTORE_TO_NETSUITE_SHIPPING_METHODS_CONFIG = None
SHOPIFY_DC_LOCATION_ID_MAP_CONFIG = None
CUSTOM_PRICE = -1


def get_param_store():
    global PARAM_STORE  # pylint: disable=W0603
    if not PARAM_STORE:
        tenant = os.environ.get('TENANT')
        stage = os.environ.get('STAGE')
        PARAM_STORE = ParamStore(tenant=tenant, stage=stage)
    return PARAM_STORE


def get_newstore_config():
    global NEWSTORE_CONFIG  # pylint: disable=W0603
    if not NEWSTORE_CONFIG:
        NEWSTORE_CONFIG = json.loads(get_param_store().get_param('newstore'))
    return NEWSTORE_CONFIG


def get_netsuite_config():
    global NETSUITE_CONFIG  # pylint: disable=W0603
    if not NETSUITE_CONFIG:
        NETSUITE_CONFIG = json.loads(get_param_store().get_param('netsuite'))
    return NETSUITE_CONFIG


def get_newstore_to_netsuite_channel_config():
    global NEWSTORE_TO_NETSUITE_CHANNEL_CONFIG  # pylint: disable=W0603
    if not NEWSTORE_TO_NETSUITE_CHANNEL_CONFIG:
        NEWSTORE_TO_NETSUITE_CHANNEL_CONFIG = json.loads(
            get_param_store().get_param('netsuite/newstore_to_netsuite_channel'))
    return NEWSTORE_TO_NETSUITE_CHANNEL_CONFIG


def get_newstore_to_netsuite_locations_config():
    global NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG  # pylint: disable=W0603
    if not NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG:
        NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG = json.loads(
            get_param_store().get_param('netsuite/newstore_to_netsuite_locations'))
    return NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG

def get_newstore_fulfillment_rds():
    global NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG  # pylint: disable=W0603
    if not NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG:
        NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG = json.loads(
            get_param_store().get_param('fulfillment_rds'))
    return NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG


def get_newstore_to_netsuite_payment_items_config():
    global NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS_CONFIG  # pylint: disable=W0603
    if not NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS_CONFIG:
        NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS_CONFIG = json.loads(
            get_param_store().get_param('netsuite/newstore_to_netsuite_payment_items'))
    return NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS_CONFIG


def get_giftcard_product_ids_config():
    global NEWSTORE_GIFTCARD_PRODUCT_IDS_CONFIG  # pylint: disable=W0603
    if not NEWSTORE_GIFTCARD_PRODUCT_IDS_CONFIG:
        NEWSTORE_GIFTCARD_PRODUCT_IDS_CONFIG = get_param_store().get_param(
            'netsuite/newstore_giftcard_product_ids').split(',')
    return NEWSTORE_GIFTCARD_PRODUCT_IDS_CONFIG


def get_currency_list():
    return CustomerCurrencyList([
        CustomerCurrency(
            currency=RecordRef(internalId=int(get_netsuite_config()['currency_usd_internal_id']))
        ),
        CustomerCurrency(
            currency=RecordRef(internalId=int(get_netsuite_config()['currency_cad_internal_id']))
        )
    ])


def get_currency_id(currency_code):
    currency_map = {
        'USD': int(get_netsuite_config()['currency_usd_internal_id']),
        'CAD': int(get_netsuite_config()['currency_cad_internal_id']),
        'GBP': int(get_netsuite_config()['currency_gbp_internal_id']),
        'EUR': int(get_netsuite_config()['currency_eur_internal_id'])
    }
    return currency_map.get(str(currency_code))


def get_newstore_to_netsuite_shipping_methods_config():
    global NEWSTORE_TO_NETSUITE_SHIPPING_METHODS_CONFIG    # pylint: disable=W0603
    if not NEWSTORE_TO_NETSUITE_SHIPPING_METHODS_CONFIG:
        NEWSTORE_TO_NETSUITE_SHIPPING_METHODS_CONFIG = json.loads(
            get_param_store().get_param('netsuite/newstore_to_netsuite_shipping_methods'))
    return NEWSTORE_TO_NETSUITE_SHIPPING_METHODS_CONFIG


def get_not_taxable_id(subsidiary_id):
    if int(subsidiary_id) == int(get_netsuite_config().get('subsidiary_us_internal_id')):
        return get_netsuite_config()['not_taxable_us']
    if int(subsidiary_id) == int(get_netsuite_config().get('subsidiary_ca_internal_id')):
        return get_netsuite_config()['not_taxable_ca']
    raise ValueError(f"Provided subsidary ID, {subsidiary_id}, not mapped")


def get_tax_code_id(subsidiary_id):
    if int(subsidiary_id) == int(get_netsuite_config().get('subsidiary_us_internal_id')):
        return get_netsuite_config()['tax_override_us']
    if int(subsidiary_id) == int(get_netsuite_config().get('subsidiary_ca_internal_id')):
        return get_netsuite_config()['tax_override_ca']
    raise ValueError(f"Provided subsidary ID, {subsidiary_id}, not mapped")
