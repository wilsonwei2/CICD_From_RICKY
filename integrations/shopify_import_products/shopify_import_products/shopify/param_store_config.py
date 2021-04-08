import json
# From shared
from param_store.client import ParamStore


class ParamStoreConfig:
    param_store = None
    shopify_config = None
    categories_map = None

    def __init__(self, tenant, stage):
        self.tenant = tenant
        self.stage = stage

    def get_param_store(self):
        if not self.param_store:
            self.param_store = ParamStore(self.tenant, self.stage)
        return self.param_store

    def get_shopify_config(self):
        if not self.shopify_config:
            self.shopify_config = json.loads(self.get_param_store().get_param('shopify'))
        return self.shopify_config

    def get_categories_map(self):
        if not self.categories_map:
            self.categories_map = json.loads(self.get_param_store().get_param('categories_map'))
        return self.categories_map
