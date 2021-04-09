import os
import json
from param_store.client import ParamStore

TENANT = os.environ['TENANT'] or 'marine-layer'
STAGE = os.environ['STAGE'] or 'x'


class Utils:
    __instance = None
    param_store = None

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

    def get_newstore_config(self):
        return json.loads(self.get_param_store().get_param('newstore'))
