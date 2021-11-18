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
    _newstore_conn = None
    _newstore_config = {}
    _netsuite_config = {}

    @staticmethod
    def _get_param_store():
        if not Utils._param_store:
            Utils._param_store = ParamStore(tenant=TENANT,
                                            stage=STAGE)
        return Utils._param_store

    @staticmethod
    def get_newstore_conn(context=None):
        if not Utils._newstore_conn:
            Utils._newstore_conn = NewStoreConnector(
                tenant=TENANT,
                context=context,
                raise_errors=True
            )
        return Utils._newstore_conn

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
    def get_distribution_centres():
        return json.loads(Utils._get_param_store().get_param('distribution_centres'))

    @staticmethod
    def get_virtual_product_ids_config():
        return Utils._get_param_store().get_param('netsuite/newstore_virtual_product_ids').split(',')

    @staticmethod
    def get_netsuite_location_map():
        return json.loads(Utils._get_param_store().get_param('netsuite/newstore_to_netsuite_locations'))

    @staticmethod
    def is_store(store_id):
        for dist_center in Utils.get_distribution_centres():
            if dist_center.lower() == store_id.lower():
                return False
        return True

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
