import json
import os
import logging
from param_store.client import ParamStore
from newstore_adapter.connector import NewStoreConnector

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
    _newstore_config = None

    @staticmethod
    def _get_newstore_config():
        if not Utils._newstore_config:
            Utils._newstore_config = json.loads(
                Utils.get_param_store().get_param('newstore'))
        return Utils._newstore_config

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
    def get_param_store():
        if not Utils._param_store:
            Utils._param_store = ParamStore(tenant=TENANT,
                                            stage=STAGE)
        return Utils._param_store
