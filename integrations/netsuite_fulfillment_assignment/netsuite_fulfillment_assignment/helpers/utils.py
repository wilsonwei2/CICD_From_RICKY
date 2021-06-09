import os
import json
import logging
from datetime import datetime, date
from param_store.client import ParamStore
from newstore_adapter.connector import NewStoreConnector

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
    _netsuite_config = {}
    _fulfillment_config = {}
    _ns_handler = None

    @staticmethod
    def get_param_store():
        if not Utils._param_store:
            Utils._param_store = ParamStore(tenant=TENANT,
                                            stage=STAGE)
        return Utils._param_store

    @staticmethod
    def get_ns_handler(context=None):
        if not Utils._ns_handler:
            newstore_config = json.loads(Utils.get_param_store().get_param(
                os.environ.get('NEWSTORE_CREDS_PARAM', 'newstore')))
            Utils._ns_handler = NewStoreConnector(
                tenant=os.environ.get('TENANT'),
                context=context,
                host=newstore_config['host'],
                username=newstore_config['username'],
                password=newstore_config['password'],
                raise_errors=True
            )

        return Utils._ns_handler

    @staticmethod
    def get_external_order_id(uuid):
        Utils._ns_handler = Utils.get_ns_handler()
        body = Utils._ns_handler.get_external_order(uuid, id_type='id')
        external_order_id = body['external_order_id']
        LOGGER.info(f"External order id is {external_order_id}")

        return external_order_id

    @staticmethod
    def get_netsuite_config():
        if not Utils._netsuite_config:
            Utils._netsuite_config = json.loads(
                Utils.get_param_store().get_param('netsuite'))
        return Utils._netsuite_config

    @staticmethod
    def get_netsuite_service_level():
        return json.loads(Utils.get_param_store().get_param('netsuite/newstore_to_netsuite_shipping_methods'))

    @staticmethod
    def get_netsuite_location_map():
        return json.loads(Utils.get_param_store().get_param('netsuite/newstore_to_netsuite_locations'))

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
    def json_serial(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError("Type %s not serializable" % type(obj))

    @staticmethod
    def get_external_identifiers(external_identifiers, key):
        if external_identifiers:
            for attr in external_identifiers:
                if attr['type'] == key:
                    return attr['value']
        return ''

    @staticmethod
    def get_extended_attribute(extended_attributes, key):
        if not extended_attributes or not key:
            return None
        result = next(
            (item['value'] for item in extended_attributes if item['name'] == key), None)
        return result
