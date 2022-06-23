from yotpo_shopper_loyalty.handlers.newstore import NShandler
from shopify_adapter.connector import ShopifyConnector
from param_store.client import ParamStore
from pom_common.shopify import ShopManager
import os
import json

TENANT = os.environ.get('TENANT', 'frankandoak')
STAGE = os.environ.get('STAGE', 'x')
REGION = os.environ.get('REGION', 'us-east-1')


class Utils():
    __instance = None
    param_store = None
    ns_handler = None
    shopify_handlers = {}
    shopify_configs = {}
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

    def get_shopify_handlers(self):
        if len(self.shopify_handlers) == 0:
            shop_manager = ShopManager(TENANT, STAGE, REGION)

            for shop_id in shop_manager.get_shop_ids():
                current_config = shop_manager.get_shop_config(shop_id)
                self.shopify_configs[shop_id] = current_config

                self.shopify_handlers[shop_id] = ShopifyConnector(
                    api_key=current_config['username'],
                    password=current_config['password'],
                    shop=current_config['shop']
                )

        return self.shopify_handlers.values()

    def get_shopify_handler(self, shop_id):
        self.get_shopify_handlers()
        return self.shopify_handlers[shop_id] if shop_id in self.shopify_handlers else None

    def get_shop_id(self, shop_name):
        self.get_shopify_handlers()
        for shop_id, config in self.shopify_configs.items():
            if config['shop'] == shop_name:
                return shop_id
        return None

    def get_shopify_config(self, shop_name):
        self.get_shopify_handlers()
        return next(filter(lambda config: config['shop'] == shop_name, self.shopify_configs.values()), None)

    def get_shopify_service_level_map(self):
        if not self.shopify_service_level_map:
            self.shopify_service_level_map = json.loads(
                self.get_parameter_store().get_param('shopify/service_level'))
        return self.shopify_service_level_map
