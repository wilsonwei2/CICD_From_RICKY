import os
import json
import logging
from datetime import datetime, date
from pytz import timezone
from pytz.exceptions import UnknownTimeZoneError
from param_store.client import ParamStore

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

TENANT = os.environ.get('TENANT')
STAGE = os.environ.get('STAGE')
PARAM_STORE = None
NEWSTORE_CONFIG = None
NETSUITE_CONFIG = None
NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG = None


def get_param_store():
    global PARAM_STORE
    if not PARAM_STORE:
        PARAM_STORE = ParamStore(tenant=TENANT,
                                 stage=STAGE)
    return PARAM_STORE


def get_store(ns_handler, store_id):
    store = ns_handler.get_store(store_id)
    if store:
        return store
    raise ValueError(f'Unable to retrieve information from NewStore for store {store_id}')


def get_product(ns_handler, product_id, catalog, locale):
    product = ns_handler.get_product(product_id, catalog, locale)
    if product:
        return product
    raise ValueError(f'Unable to retrieve information from NewStore for product {product_id}')


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def get_nws_to_nts_locations():
    global NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG
    if not NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG:
        NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG = json.loads(get_param_store().get_param('netsuite/newstore_to_netsuite_locations'))
    LOGGER.debug(f"NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG: {json.dumps(NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG, indent=4)}")
    return NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG


def get_netsuite_config():
    global NETSUITE_CONFIG
    if not NETSUITE_CONFIG:
        NETSUITE_CONFIG = json.loads(get_param_store().get_param('netsuite'))
    return NETSUITE_CONFIG


def get_newstore_config():
    global NEWSTORE_CONFIG
    if not NEWSTORE_CONFIG:
        NEWSTORE_CONFIG = json.loads(get_param_store().get_param('newstore'))
    return NEWSTORE_CONFIG


def get_netsuite_store_mapping(nws_value):
    if not nws_value:
        return {}

    locations_config = get_nws_to_nts_locations()
    mapping = locations_config.get(nws_value)
    if mapping is None:
        # try to get mapping for pre-pended code
        mapping = locations_config.get(nws_value[:3])

    if mapping is None:
        LOGGER.error(f'Failed to obtain newstore to netsuite location mapping for \'{nws_value}\'')
        return {}

    return mapping


def get_netsuite_store_internal_id(nws_value, is_sellable=True):
    mapping = get_netsuite_store_mapping(nws_value)
    return mapping.get('id') if is_sellable else mapping.get('id_damage')


def get_one_of_these_fields(obj, fields):
    return next((obj[field] for field in fields if field in obj), None)


def get_subsidiary_from_currency(currency_id):
    subsidiary_map = {
        int(get_netsuite_config()['currency_usd_internal_id']): int(get_netsuite_config()['subsidiary_us_internal_id']),
        int(get_netsuite_config()['currency_cad_internal_id']): int(get_netsuite_config()['subsidiary_ca_internal_id'])
    }
    return subsidiary_map.get(int(currency_id))


def get_write_off_from_subsidiary(subsidiary_id, loc_type):
    write_off_map = {
        int(get_netsuite_config()['subsidiary_us_internal_id']): int(get_netsuite_config()[f'us_{loc_type}_write_off']),
        int(get_netsuite_config()['subsidiary_ca_internal_id']): int(get_netsuite_config()[f'ca_{loc_type}_write_off'])
    }
    return write_off_map.get(int(subsidiary_id))


def get_currency_from_country_code(country_code):
    currency_map = {
        'US': int(get_netsuite_config()['currency_usd_internal_id']),
        'CA': int(get_netsuite_config()['currency_cad_internal_id']),
        'GB': int(get_netsuite_config()['currency_gbp_internal_id']),
        'EU': int(get_netsuite_config()['currency_eur_internal_id'])
    }
    return currency_map.get(str(country_code))


def format_datestring_for_netsuite(date_string, time_zone, cutoff_index=22, format_string='%Y-%m-%dT%H:%M:%S.%f'):
    tran_date = datetime.strptime(date_string[:cutoff_index], format_string)
    tran_date = tran_date.replace(tzinfo=timezone('UTC'))
    try:
        tran_date = tran_date.astimezone(timezone(time_zone))
    except UnknownTimeZoneError:
        LOGGER.warning(f'Invalid timezone {time_zone}, defaulting to America/New_York')
        tran_date = tran_date.astimezone(timezone('America/New_York'))
    return tran_date


def get_nws_location_id(nws_store_fulfillment_node):
    store_config = get_nws_to_nts_locations()
    for location_id in store_config:
        if store_config[location_id]['ff_node_id'] == nws_store_fulfillment_node:
            return location_id
    return None
