from shopify_import_order.handlers.newstore import NShandler
from shopify_adapter.connector import ShopifyConnector
from param_store.client import ParamStore
import os
import json

TENANT = os.environ.get('TENANT', 'frankandoak')
STAGE = os.environ.get('STAGE', 'x')


class Utils():
    __instance = None
    param_store = None
    ns_handler = None
    shopify_handler = None
    shopify_service_level_map = None

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

    def get_parameter_store(self, tenant=TENANT, stage=STAGE):
        if not self.param_store:
            self.param_store = ParamStore(tenant, stage)
        return self.param_store

    def get_ns_handler(self):
        if not self.ns_handler:
            newstore_creds = json.loads(
                self.get_parameter_store().get_param('newstore'))
            self.ns_handler = NShandler(
                host=newstore_creds['host'],
                username=newstore_creds['username'],
                password=newstore_creds['password']
            )
        return self.ns_handler

    def get_shopify_handler(self):
        if not self.shopify_handler:
            shopify_config = json.loads(self.get_parameter_store().get_param('shopify'))
            self.shopify_handler = ShopifyConnector(
                api_key=shopify_config['username'],
                password=shopify_config['password'],
                shop=shopify_config['shop']
            )
        return self.shopify_handler

    def get_shopify_service_level_map(self):
        if not self.shopify_service_level_map:
            self.shopify_service_level_map = json.loads(
                self.get_parameter_store().get_param('shopify/service_level'))
        return self.shopify_service_level_map
