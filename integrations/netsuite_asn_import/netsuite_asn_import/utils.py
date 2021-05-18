import os
import json
import logging
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
    _newstore_to_netsuite_locations = {}

    @staticmethod
    def get_newstore_conn(context=None):
        if not Utils._newstore_conn:
            newstore_config = Utils.get_newstore_config()
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
    def get_param_store():
        if not Utils._param_store:
            Utils._param_store = ParamStore(tenant=TENANT,
                                            stage=STAGE)
        return Utils._param_store

    @staticmethod
    def get_newstore_config():
        return json.loads(Utils.get_param_store().get_param('newstore'))

    @staticmethod
    def get_netsuite_config():
        return json.loads(Utils.get_param_store().get_param('netsuite'))

    @staticmethod
    def get_netsuite_location_map():
        if not Utils._newstore_to_netsuite_locations:
            Utils._newstore_to_netsuite_locations = json.loads(
                Utils.get_param_store().get_param('netsuite/newstore_to_netsuite_locations'))
        return Utils._newstore_to_netsuite_locations
