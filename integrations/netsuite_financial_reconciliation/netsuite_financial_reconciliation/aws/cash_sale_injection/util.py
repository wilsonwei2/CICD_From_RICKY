import logging
import json
import os
import csv
from datetime import datetime, date

# Runs startup processes (expecting to be 'unused')
import netsuite.netsuite_environment_loader  # pylint: disable=W0611
import netsuite.api.customer as nsac
from netsuite.service import (
    CustomerAddressbook,
    CustomerAddressbookList,
    RecordRef,
    CustomerCurrency,
    CustomerCurrencyList
)
from param_store.client import ParamStore

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

TRUE_VALUES = ['1', 'yes', 'true', 1, True, 'TRUE']

PARAM_STORE = None
NETSUITE_CONFIG = None
NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG = None
NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS_CONFIG = None
NEWSTORE_TO_NETSUITE_PAYMENT_ACCOUNT_CONFIG = None
NEWSTORE_GIFTCARD_PRODUCT_IDS_CONFIG = None
DC_TIMEZONE_MAPPING_CONFIG = None
NEWSTORE_TO_NETSUITE_CHANNEL_CONFIG = None
NEWSTORE_TO_NETSUITE_SHIPPING_METHODS_CONFIG = None

CUSTOM_PRICE = -1


def get_param_store():
    global PARAM_STORE  # pylint: disable=W0603
    if not PARAM_STORE:
        tenant = os.environ.get('TENANT')
        stage = os.environ.get('STAGE')
        PARAM_STORE = ParamStore(tenant=tenant,
                                 stage=stage)
    return PARAM_STORE


def get_netsuite_config():
    global NETSUITE_CONFIG  # pylint: disable=W0603
    # TODO - enable the next line again once the configuration is stable pylint: disable=fixme
    # if not NETSUITE_CONFIG:
    NETSUITE_CONFIG = json.loads(get_param_store().get_param('netsuite'))
    return NETSUITE_CONFIG


def get_newstore_to_netsuite_locations_config():
    global NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG  # pylint: disable=W0603
    # TODO - enable the next line again once the configuration is stable pylint: disable=fixme
    # if not NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG:
    NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG = json.loads(
        get_param_store().get_param('netsuite/newstore_to_netsuite_locations'))
    return NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG


def get_newstore_to_netsuite_payment_items_config():
    global NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS_CONFIG  # pylint: disable=W0603
    # TODO - enable the next line again once the configuration is stable pylint: disable=fixme
    # if not NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS_CONFIG:
    NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS_CONFIG = json.loads(
        get_param_store().get_param('netsuite/newstore_to_netsuite_payment_items'))
    return NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS_CONFIG

def get_newstore_to_netsuite_payment_account_config():
    global NEWSTORE_TO_NETSUITE_PAYMENT_ACCOUNT_CONFIG  # pylint: disable=W0603
    if not NEWSTORE_TO_NETSUITE_PAYMENT_ACCOUNT_CONFIG:
        NEWSTORE_TO_NETSUITE_PAYMENT_ACCOUNT_CONFIG = json.loads(
            get_param_store().get_param('netsuite/newstore_to_netsuite_payment_methods'))
    return NEWSTORE_TO_NETSUITE_PAYMENT_ACCOUNT_CONFIG

def get_giftcard_product_ids_config():
    global NEWSTORE_GIFTCARD_PRODUCT_IDS_CONFIG  # pylint: disable=W0603
    if not NEWSTORE_GIFTCARD_PRODUCT_IDS_CONFIG:
        NEWSTORE_GIFTCARD_PRODUCT_IDS_CONFIG = get_param_store().get_param(
            'netsuite/newstore_giftcard_product_ids').split(',')
    return NEWSTORE_GIFTCARD_PRODUCT_IDS_CONFIG


def get_dc_timezone_mapping_config():
    global DC_TIMEZONE_MAPPING_CONFIG  # pylint: disable=W0603
    if not DC_TIMEZONE_MAPPING_CONFIG:
        DC_TIMEZONE_MAPPING_CONFIG = json.loads(get_param_store().get_param('netsuite/dc_timezone_mapping'))
    return DC_TIMEZONE_MAPPING_CONFIG


def get_newstore_to_netsuite_channel_config():
    global NEWSTORE_TO_NETSUITE_CHANNEL_CONFIG  # pylint: disable=W0603
    if not NEWSTORE_TO_NETSUITE_CHANNEL_CONFIG:
        NEWSTORE_TO_NETSUITE_CHANNEL_CONFIG = json.loads(
            get_param_store().get_param('netsuite/newstore_to_netsuite_channel'))
    return NEWSTORE_TO_NETSUITE_CHANNEL_CONFIG


def get_newstore_to_netsuite_shipping_methods_config():
    global NEWSTORE_TO_NETSUITE_SHIPPING_METHODS_CONFIG  # pylint: disable=W0603
    # TODO - enable the next line again once the configuration is stable pylint: disable=fixme
    # if not NEWSTORE_TO_NETSUITE_SHIPPING_METHODS_CONFIG:
    NEWSTORE_TO_NETSUITE_SHIPPING_METHODS_CONFIG = json.loads(
        get_param_store().get_param('netsuite/newstore_to_netsuite_shipping_methods'))
    return NEWSTORE_TO_NETSUITE_SHIPPING_METHODS_CONFIG


def get_netsuite_store_mapping(nws_value):
    if not nws_value:
        return {}

    locations_config = get_newstore_to_netsuite_locations_config()
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


async def get_customer_order(ns_handler, order_id):
    customer_order = ns_handler.get_customer_order(order_id)
    if customer_order:
        LOGGER.info(f"Customer order: \n{json.dumps(customer_order['customer_order'], indent=4)}")
        return customer_order['customer_order']
    return None


def is_historic_order(message):
    LOGGER.debug(f"Running is_historic_order with message: {json.dumps(message)}")
    order = message.get('order', {})
    return check_true(order.get('is_historical'))


def check_true(value):
    if not value:
        return False
    return value in TRUE_VALUES


def is_endless_aisle(order_payload):
    return order_payload.get('channel_type', '') == 'store' and \
           order_payload['shipment_details'][0]['shipping_option']['shipping_type'] == 'traditional_carrier'


def get_currency_list():
    return CustomerCurrencyList([
        CustomerCurrency(
            currency=RecordRef(internalId=int(get_netsuite_config()['currency_usd_internal_id']))
        ),
        CustomerCurrency(
            currency=RecordRef(internalId=int(get_netsuite_config()['currency_cad_internal_id']))
        )
    ])


async def get_store(ns_handler, store_id):
    store = ns_handler.get_store(store_id)
    if store:
        return store
    raise ValueError(f'Unable to retrieve information from NewStore for store {store_id}')


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def get_extended_attribute(extended_attributes, key):
    if not extended_attributes or not key:
        return None
    result = next((item['value'] for item in extended_attributes if item['name'] == key), None)
    return result


def get_or_create_customer(order_data):
    customer = order_data['customer']
    shipping_addr = order_data.get('shipping_address')
    billing_addr = order_data.get('billing_address')

    addressbook = []
    if shipping_addr:
        addressbook.append(CustomerAddressbook(**shipping_addr))

    if billing_addr:
        addressbook.append(CustomerAddressbook(**billing_addr))

    if addressbook:
        addr_book_list = {
            'replaceAll': True,
            'addressbook': addressbook
        }
        customer_addr_book_list = CustomerAddressbookList(**addr_book_list)
        customer['addressbookList'] = customer_addr_book_list

    # If customer is found we update it, but only if it is the same subsidiary
    netsuite_customer_internal_id = nsac.lookup_customer_id_by_email(customer)
    if netsuite_customer_internal_id:
        LOGGER.info('Customer exists, we will update it')
        customer['internalId'] = netsuite_customer_internal_id
        return nsac.update_customer(customer)

    LOGGER.info('Create new Customer.')
    # This returns the Customer or None if there is any error
    return nsac.create_customer(customer)


def order_has_gift_cards(order):
    for item in order['items']:
        if item['product_id'] in get_giftcard_product_ids_config():
            return True
    return False


def is_product_gift_card(product_id):
    return product_id in get_giftcard_product_ids_config()


def get_one_of_these_fields(source, fields):
    return next((source[field] for field in fields if field in source), None)


def get_subsidiary_id(store_id):
    newstore_to_netsuite_locations = get_newstore_to_netsuite_locations_config()
    subsidiary_id = newstore_to_netsuite_locations.get(store_id, {}).get('subsidiary_id')

    if not subsidiary_id:
        raise ValueError(f"Unable to find subsidiary for NewStore location '{store_id}'.")
    return subsidiary_id


def get_currency_id_from_country_code(country_code):
    currency_map = {
        'US': int(get_netsuite_config()['currency_usd_internal_id']),
        'CA': int(get_netsuite_config()['currency_cad_internal_id']),
        'GB': int(get_netsuite_config()['currency_gbp_internal_id']),
        'EU': int(get_netsuite_config()['currency_eur_internal_id'])
    }
    return currency_map.get(str(country_code))


def get_currency_id(currency_code):
    currency_map = {
        'USD': int(get_netsuite_config()['currency_usd_internal_id']),
        'CAD': int(get_netsuite_config()['currency_cad_internal_id']),
        'GBP': int(get_netsuite_config()['currency_gbp_internal_id']),
        'EUR': int(get_netsuite_config()['currency_eur_internal_id'])
    }
    return currency_map.get(str(currency_code))


def get_countries():
    countries = {}
    filename = os.path.join(os.path.dirname(__file__), 'iso_country_codes.csv')
    with open(filename) as file:
        content = csv.DictReader(file, delimiter=',')
        for line in content:
            countries[line['Alpha-2 code']] = line['NetSuite code']
    return countries


async def replace_associate_id_for_email(ns_handler, customer_order):
    associate_id = customer_order['associate_id']
    if not associate_id:
        return
    employee = ns_handler.get_employee(associate_id)
    if employee:
        customer_order['associate_id'] = employee['email']


def require_shipping(item):
    requires_shipping = get_extended_attribute(item.get('extended_attributes'), 'requires_shipping')
    # If it's requires_shipping is None assume that it needs shipping
    return requires_shipping is None or requires_shipping.lower() == 'true'


def check_golive_date(event_date):
    golive_date = get_netsuite_config().get('golive_date', '')[:19]
    event_date = event_date[:19]
    if golive_date:
        return datetime.strptime(golive_date, "%Y-%m-%dT%H:%M:%S") < datetime.strptime(event_date, "%Y-%m-%dT%H:%M:%S")
    return False
