import os
import json
import logging
from param_store.client import ParamStore
from newstore_adapter.connector import NewStoreConnector
from pom_common.shopify import ShopManager
from shopify_fulfillment.helpers.shopify_handler import ShopifyConn

LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOG_LEVEL)
TENANT = os.environ.get('TENANT')
STAGE = os.environ.get('STAGE')
REGION = os.environ.get('REGION', 'us-east-1')


class Utils():
    _param_store = None
    _shopify_conns = {}
    _newstore_conn = None

    @staticmethod
    def get_newstore_conn(context=None):
        if not Utils._newstore_conn:
            newstore_creds = json.loads(
                Utils.get_param_store().get_param('newstore'))
            Utils._newstore_conn = NewStoreConnector(tenant=newstore_creds['tenant'], context=context,
                                                     username=newstore_creds['username'],
                                                     password=newstore_creds['password'], host=newstore_creds['host'],
                                                     raise_errors=True)
        return Utils._newstore_conn

    @staticmethod
    def get_shopify_conns():
        if len(Utils._shopify_conns) == 0:
            shop_manager = ShopManager(TENANT, STAGE, REGION)

            for shop_id in shop_manager.get_shop_ids():
                shopify_config = shop_manager.get_shop_config(shop_id)
                currency = shopify_config['currency']

                Utils._shopify_conns[currency] = ShopifyConn(
                    shopify_config['username'],
                    shopify_config['password'],
                    shopify_config['shop']
                )

        return Utils._shopify_conns.values()

    @staticmethod
    def get_shopify_conn(currency):
        if len(Utils._shopify_conns) == 0:
            Utils.get_shopify_conns()

        return Utils._shopify_conns[currency]

    @staticmethod
    def get_param_store():
        if not Utils._param_store:
            Utils._param_store = ParamStore(tenant=TENANT,
                                            stage=STAGE)
        return Utils._param_store

    @staticmethod
    def get_shopify_dc_location_id_map():
        return json.loads(Utils.get_param_store().get_param('shopify/dc_location_id_map'))

    @staticmethod
    def check_true(value):
        if not value:
            return False
        return value in ('1', 'yes', 'true', 1, True, 'TRUE')

    @staticmethod
    def get_shopify_channel(customer_order):
        extended_attributes = customer_order.get('extended_attributes', [])
        key = 'ext_channel_name'
        shopify_channel = Utils.get_extended_attribute(extended_attributes=extended_attributes,
                                                       key=key)
        return shopify_channel

    @staticmethod
    def is_historic_order(message):
        LOGGER.debug(f"Running is_historic_order with message: {json.dumps(message)}")
        order = message.get('order', {})
        if order.get('sales_order_external_id', '').startswith('HIST'):
            return True
        return Utils.check_true(order.get('is_historical'))

    @staticmethod
    def is_endless_aisle(order_payload):
        return order_payload.get('channel_type', '') == 'store' and \
            order_payload['shipment_details'][0]['shipping_option']['shipping_type'] == 'traditional_carrier'

    @staticmethod
    def get_extended_attribute(extended_attributes, key):
        if not extended_attributes or not key:
            return None
        result = next((item['value'] for item in extended_attributes if item['name'] == key), None)
        return result
