# pylint: disable=R0904

import os
import math
import json
import logging
import numbers
import csv
from datetime import datetime, date
from pytz import timezone
from pytz.exceptions import UnknownTimeZoneError
from param_store.client import ParamStore
from pom_common.shopify import ShopManager
from newstore_adapter.connector import NewStoreConnector
from shopify_adapter.connector import ShopifyConnector

LOGGER = logging.getLogger(__file__)
LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'info').upper() or 'INFO'
LOG_LEVEL = getattr(logging, LOG_LEVEL_SET, None)
if not isinstance(LOG_LEVEL, int):
    LOG_LEVEL = getattr(logging, 'INFO', None)
LOGGER.setLevel(LOG_LEVEL)
TENANT = os.environ.get('TENANT')
STAGE = os.environ.get('STAGE')
REGION = os.environ.get('REGION')


class Utils():
    _countries = {}
    _param_store = None
    _newstore_conn = None
    _newstore_config = {}
    _shopify_conn = {}
    _shopify_config = {}
    _netsuite_config = {}
    _newstore_to_netsuite_locations = {}
    _newstore_to_netsuite_payments = {}
    _newstore_to_netsuite_payment_methods = {}  # pylint: disable=invalid-name
    _newstore_giftcard_ids = ''
    _dc_timezone_mapping = {}
    _newstore_to_netsuite_channels = {}

    @staticmethod
    def get_newstore_conn(context=None):
        if not Utils._newstore_conn:
            newstore_creds = Utils._get_newstore_config()
            Utils._newstore_conn = NewStoreConnector(tenant=newstore_creds['tenant'], context=context,
                                                     username=newstore_creds['username'],
                                                     password=newstore_creds['password'], host=newstore_creds['host'],
                                                     raise_errors=True)
        return Utils._newstore_conn

    @staticmethod
    def get_shopify_conn(currency):
        if not currency in Utils._shopify_conn:
            shop_manager = ShopManager(TENANT, STAGE, REGION)

            for shop_id in shop_manager.get_shop_ids():
                shopify_config = shop_manager.get_shop_config(shop_id)

                Utils._shopify_conn[shopify_config['currency']] = ShopifyConnector(
                    shopify_config['username'],
                    shopify_config['password'],
                    shopify_config['shop']
                )

        return Utils._shopify_conn[currency]

    @staticmethod
    def _get_param_store():
        if not Utils._param_store:
            Utils._param_store = ParamStore(tenant=TENANT,
                                            stage=STAGE)
        return Utils._param_store

    @staticmethod
    def _get_newstore_config():
        if not Utils._newstore_config:
            Utils._newstore_config = json.loads(
                Utils._get_param_store().get_param('newstore'))
        return Utils._newstore_config

    @staticmethod
    def get_netsuite_config():
        if not Utils._netsuite_config:
            Utils._netsuite_config = json.loads(
                Utils._get_param_store().get_param('netsuite'))
        return Utils._netsuite_config

    @staticmethod
    def get_netsuite_location_map():
        if not Utils._newstore_to_netsuite_locations:
            Utils._newstore_to_netsuite_locations = json.loads(Utils._get_param_store().get_param(
                'netsuite/newstore_to_netsuite_locations'))
        return Utils._newstore_to_netsuite_locations

    @staticmethod
    def get_nws_to_netsuite_payment(payment_type):
        if payment_type == 'methods':
            if not Utils._newstore_to_netsuite_payment_methods:
                Utils._newstore_to_netsuite_payment_methods = json.loads(
                    Utils._get_param_store().get_param(
                        f'netsuite/newstore_to_netsuite_payment_{payment_type}')
                )
            return Utils._newstore_to_netsuite_payment_methods

        # payment type is 'items'
        if not Utils._newstore_to_netsuite_payments:
            Utils._newstore_to_netsuite_payments = json.loads(
                Utils._get_param_store().get_param(
                    f'netsuite/newstore_to_netsuite_payment_{payment_type}')
            )
        return Utils._newstore_to_netsuite_payments

    @staticmethod
    def _get_giftcard_product_ids():
        if not Utils._newstore_giftcard_ids:
            Utils._newstore_giftcard_ids = Utils._get_param_store().get_param(
                'netsuite/newstore_giftcard_product_ids').split(',')
        return Utils._newstore_giftcard_ids

    @staticmethod
    def get_dc_timezone_mapping_config():
        if not Utils._dc_timezone_mapping:
            Utils._dc_timezone_mapping = json.loads(
                Utils._get_param_store().get_param('netsuite/dc_timezone_mapping')
            )
        return Utils._dc_timezone_mapping

    @staticmethod
    def get_nws_to_netsuite_channel():
        if not Utils._newstore_to_netsuite_channels:
            Utils._newstore_to_netsuite_channels = json.loads(
                Utils._get_param_store().get_param('netsuite/newstore_to_netsuite_channel')
            )
        return Utils._newstore_to_netsuite_channels

    @staticmethod
    def _get_netsuite_store_mapping(nws_value):
        if not nws_value:
            return {}

        locations_config = Utils.get_netsuite_location_map()
        mapping = locations_config.get(nws_value)

        if mapping is None:
            LOGGER.error(
                f'Failed to obtain newstore to netsuite location mapping for \'{nws_value}\'')
            return {}

        return mapping

    @staticmethod
    def get_netsuite_store_internal_id(nws_value, is_sellable=True):
        mapping = Utils._get_netsuite_store_mapping(nws_value)
        return mapping.get('id') if is_sellable else mapping.get('id_damage')

    @staticmethod
    def is_endless_aisle(order_payload):
        if order_payload.get('channel_type', '') == 'store':
            for shipping_option in order_payload['shipment_details']:
                if shipping_option['shipping_option']['shipping_type'] == 'traditional_carrier' or \
                    shipping_option['shipping_option']['shipping_type'] == 'same_day_delivery':
                    return True
        return False

    @staticmethod
    def get_extended_attribute(extended_attributes, key):
        if not extended_attributes or not key:
            return None
        result = next(
            (item['value'] for item in extended_attributes if item['name'] == key), None)
        return result

    @staticmethod
    def is_product_gift_card(product_id):
        return product_id in Utils._get_giftcard_product_ids()

    @staticmethod
    def get_one_of_these_fields(params, fields):
        if params is None:
            params = {}
        if fields is None:
            fields = []

        return next((params[field] for field in fields if field in params), None)

    @staticmethod
    def verify_all_transac_refunded(refund_transactions, refund_total):
        total = 0
        for trans in refund_transactions:
            total += abs(trans['refund_amount']) \
                if trans['reason'] == 'refund' or trans['capture_amount'] == 0 else abs(trans['capture_amount'])

        refund_total = round(refund_total, 2)
        total = round(total, 2)
        if math.isclose(total, refund_total, rel_tol=0.01):
            return True
        LOGGER.error("Total of refund doesn't match with total of refunded payments. "
                     f"Refund total: {refund_total}; Refunded total: {total}")
        return False

    @staticmethod
    def verify_all_payments_refunded(payment_items, total_refund_amount):
        total = 0
        for payment in payment_items:
            total += abs(payment['amount'])
        total = round(total, 2)
        total_refund_amount = round(total_refund_amount, 2)
        if math.isclose(total, total_refund_amount, rel_tol=0.01):
            return True
        LOGGER.error("Total of refunds doesn't match with total of refunded payments. "
                     f"Refund total: {total_refund_amount}; Refunded total: {total}")
        return False

    @staticmethod
    def format_datestring_for_netsuite(date_string, time_zone, cutoff_index=19, format_string='%Y-%m-%dT%H:%M:%S'):
        time_zone = Utils.get_netsuite_config().get(
            'NETSUITE_DATE_TIMEZONE', 'America/New_York')
        tran_date = datetime.strptime(
            date_string[:cutoff_index], format_string)
        tran_date = tran_date.replace(tzinfo=timezone('UTC'))
        try:
            tran_date = tran_date.astimezone(timezone(time_zone))
        except UnknownTimeZoneError:
            LOGGER.warning(
                f'Invalid timezone {time_zone}, defaulting to America/New_York')
            tran_date = tran_date.astimezone(timezone('America/New_York'))
        return tran_date

    @staticmethod
    def json_serial(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError("Type %s not serializable" % type(obj))

    @staticmethod
    def require_shipping(item):
        requires_shipping = Utils.get_extended_attribute(
            item.get('extended_attributes'), 'requires_shipping')
        # If it's requires_shipping is None assume that it needs shipping
        return requires_shipping is None or requires_shipping.lower() == 'true'

    @staticmethod
    def get_payment_item_id(payment_method, payment_provider, currency, payment_type):
        payment_item_id = None
        payment_config = {}
        if payment_provider:
            payment_config = Utils.get_nws_to_netsuite_payment(payment_type)[payment_method].get(
                payment_provider, None)
            # For BOPIS shopify/returnly orders, this fallback is needed for paypal, sezzle etc.
            if not payment_config:
                payment_config = Utils.get_nws_to_netsuite_payment(payment_type).get(
                    payment_method, {})
        else:
            payment_config = Utils.get_nws_to_netsuite_payment(payment_type).get(
                payment_method, {})
        if isinstance(payment_config, numbers.Number):
            payment_item_id = payment_config
        else:
            payment_item_id = payment_config.get(currency.lower(), '')

        return payment_item_id

    @staticmethod
    def get_payment_method_internal_id(payment_method, payment_provider, currency, payment_type):
        payment_item_id = None
        if payment_method == 'credit_card':
            payment_item_id = Utils.get_payment_item_id(
                payment_method, payment_provider, currency, payment_type)
        elif payment_method == 'gift_card':
            payment_item_id = Utils.get_nws_to_netsuite_payment(payment_type).get(
                payment_method, {}).get(currency, '')
        else:
            payment_item_id = Utils.get_payment_item_id(
                payment_method, None, currency, payment_type)
        return payment_item_id

    @staticmethod
    def get_currency_id(currency_code):
        currency_map = {
            'USD': int(Utils.get_netsuite_config()['currency_usd_internal_id']),
            'CAD': int(Utils.get_netsuite_config()['currency_cad_internal_id']),
            'GBP': int(Utils.get_netsuite_config()['currency_gbp_internal_id']),
            'EUR': int(Utils.get_netsuite_config()['currency_eur_internal_id'])
        }
        return currency_map.get(str(currency_code))

    @staticmethod
    def get_countries():
        if not Utils._countries:
            filename = os.path.join(os.path.dirname(
                __file__), 'iso_country_codes.csv')
            with open(filename) as countries_file:
                file = csv.DictReader(countries_file, delimiter=',')
                for line in file:
                    Utils._countries[line['Alpha-2 code']] = Utils._format_country_name(
                        line['English short name lower case'])
        return Utils._countries

    @staticmethod
    def _format_country_name(country_name):
        func = lambda s: s[:1].lower() + s[1:] if s else ''
        return f'_{func(country_name).replace(" ", "")}'
