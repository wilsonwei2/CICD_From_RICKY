import os
import json
import logging
from datetime import datetime, date
from param_store.client import ParamStore
from newstore_adapter.connector import NewStoreConnector

LOGGER = logging.getLogger()
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
    _payments_config = {}
    _payment_ids = []
    _newstore_conn = None
    _newstore_config = {}

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
    def get_newstore_conn(context=None):
        if not Utils._newstore_conn:
            newstore_creds = Utils._get_newstore_config()
            Utils._newstore_conn = NewStoreConnector(tenant=newstore_creds['tenant'], context=context,
                                                     username=newstore_creds['username'],
                                                     password=newstore_creds['password'], host=newstore_creds['host'],
                                                     raise_errors=True)
        return Utils._newstore_conn

    @staticmethod
    def get_netsuite_config():
        if not Utils._netsuite_config:
            Utils._netsuite_config = json.loads(
                Utils._get_param_store().get_param('netsuite'))
        return Utils._netsuite_config

    @staticmethod
    def _get_all_values(items):
        if isinstance(items, dict):
            for value in items.values():
                yield from Utils._get_all_values(value)
        elif isinstance(items, list):
            for value in items:
                yield from Utils._get_all_values(value)
        else:
            yield items

    @staticmethod
    def _get_payments_config():
        if not Utils._payments_config:
            Utils._payments_config = json.loads(
                Utils._get_param_store().get_param('netsuite/newstore_to_netsuite_payment_items'))
        return Utils._payments_config

    @staticmethod
    def get_payment_ids():
        if not Utils._payment_ids:
            payments = Utils._get_payments_config()
            Utils._payment_ids = [int(payment_id) for payment_id in Utils._get_all_values(payments)]
        return Utils._payment_ids

    @staticmethod
    def get_tax_rounding_adj_id():
        return int(Utils.get_netsuite_config()['tax_rounding_adj_item_id'])

    @staticmethod
    def json_serial(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError("Type %s not serializable" % type(obj))
