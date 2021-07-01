import json
# From shared
from param_store.client import ParamStore


class ParamStoreConfig:
    param_store = None
    shopify_config = None
    newstore_config = None
    shopify_custom_size_mapping = None

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

    def get_newstore_config(self):
        if not self.newstore_config:
            self.newstore_config = json.loads(self.get_param_store().get_param('newstore'))
        return self.newstore_config

    def get_shopify_custom_size_mapping(self):
        if not self.shopify_custom_size_mapping:
            self.shopify_custom_size_mapping = json.loads(self.get_param_store().get_param('shopify/custom_size_mapping'))
        return self.shopify_custom_size_mapping
