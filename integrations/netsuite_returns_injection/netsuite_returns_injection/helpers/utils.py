import os
import math
import json
import logging
from datetime import datetime, date
from pytz import timezone
from pytz.exceptions import UnknownTimeZoneError
from param_store.client import ParamStore
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


class Utils():
    _param_store = None
    _newstore_conn = None
    _newstore_config = {}
    _shopify_conn = None
    _shopify_config = {}
    _netsuite_config = {}
    _newstore_to_netsuite_locations = {}
    _newstore_to_netsuite_payments = {}
    _newstore_giftcard_ids = ''
    _dc_timezone_mapping = {}
    _newstore_to_netsuite_channels = {}

    @staticmethod
    def get_newstore_conn(context=None):
        if not Utils._newstore_conn:
            newstore_config = Utils._get_newstore_config()
            Utils._newstore_conn = NewStoreConnector(
                tenant=TENANT,
                context=context,
                host=newstore_config['host'],
                username=newstore_config['username'],
                password=newstore_config['password'],
                raise_errors=True
            )
        return Utils._newstore_conn

    @staticmethod
    def get_shopify_conn():
        if not Utils._shopify_conn:
            shopify_config = Utils._get_shopify_config()
            Utils._shopify_conn = ShopifyConnector(
                api_key=shopify_config['username'],
                password=shopify_config['password'],
                shop=shopify_config['shop']
            )
        return Utils._shopify_conn

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
    def _get_shopify_config():
        if not Utils._shopify_config:
            Utils._shopify_config = json.loads(
                Utils._get_param_store().get_param('shopify'))
        return Utils._shopify_config

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
    def get_nws_to_netsuite_payment():
        if not Utils._newstore_to_netsuite_payments:
            Utils._newstore_to_netsuite_payments = json.loads(
                Utils._get_param_store().get_param('netsuite/newstore_to_netsuite_payment_items')
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
    def get_netsuite_tax_override(nws_value):
        mapping = Utils._get_netsuite_store_mapping(nws_value)
        return mapping.get('tax_override')

    @staticmethod
    def get_tax_code_id(subsidiary_id):
        if int(subsidiary_id) == int(Utils.get_netsuite_config().get('subsidiary_us_internal_id')):
            return Utils.get_netsuite_config()['tax_override_us']
        if int(subsidiary_id) == int(Utils.get_netsuite_config().get('subsidiary_ca_internal_id')):
            return Utils.get_netsuite_config()['tax_override_ca']
        raise ValueError(f"Provided subsidary ID, {subsidiary_id}, not mapped")

    @staticmethod
    def get_not_taxable_id(subsidiary_id):
        if int(subsidiary_id) == int(Utils.get_netsuite_config().get('subsidiary_us_internal_id')):
            return Utils.get_netsuite_config()['not_taxable_us']
        if int(subsidiary_id) == int(Utils.get_netsuite_config().get('subsidiary_ca_internal_id')):
            return Utils.get_netsuite_config()['not_taxable_ca']
        raise ValueError(f"Provided subsidary ID, {subsidiary_id}, not mapped")

    @staticmethod
    def is_endless_aisle(order_payload):
        return order_payload.get('channel_type', '') == 'store' and \
            order_payload['shipment_details'][0]['shipping_option']['shipping_type'] == 'traditional_carrier'

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
            total += abs(trans['refund_amount']
                         ) if trans['reason'] == 'refund' or trans['capture_amount'] == 0 else abs(trans['capture_amount'])

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
        requires_shipping = Utils.get_extended_attribute(item.get('extended_attributes'), 'requires_shipping')
        # If it's requires_shipping is None assume that it needs shipping
        return requires_shipping is None or requires_shipping.lower() == 'true'
