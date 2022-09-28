import os
import json
from param_store.client import ParamStore
from newstore_adapter.connector import NewStoreConnector


TENANT = os.environ['TENANT'] or 'frankandoak'
STAGE = os.environ['STAGE'] or 'x'


class Utils:
    __instance = None
    param_store = None
    _newstore_conn = None
    _newstore_config = {}
    _newstore_tenant = None

    @staticmethod
    def get_instance():
        """ Static access method. """
        if Utils.__instance is None:
            Utils()
        return Utils.__instance

    def __init__(self):
        """ Virtually private constructor. """
        if Utils.__instance is not None:
            raise Exception("This class is a singleton!")
        Utils.__instance = self

    def get_param_store(self):
        if not self.param_store:
            self.param_store = ParamStore(TENANT, STAGE)
        return self.param_store

    def get_newstore_conn(self, context=None):
        if not Utils._newstore_conn:
            newstore_creds = self.get_newstore_config()
            self.newstore_conn = NewStoreConnector(tenant=newstore_creds['tenant'], context=context,
                                                   username=newstore_creds['username'],
                                                   password=newstore_creds['password'], host=newstore_creds['host'],
                                                   raise_errors=True)
        return self.newstore_conn

    def get_newstore_tenant(self):
        if not Utils._newstore_tenant:
            newstore_creds = self.get_newstore_config()
            self._newstore_tenant = newstore_creds['tenant']

        return self._newstore_tenant

    def get_distribution_centres(self):
        return json.loads(self.get_param_store().get_param('distribution_centres'))

    def get_newstore_config(self):
        return json.loads(self.get_param_store().get_param('newstore'))

    def get_netsuite_config(self):
        return json.loads(self.get_param_store().get_param('netsuite'))
