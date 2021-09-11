from param_store.client import ParamStore
from pom_common.shopify import ShopManager


class ParamStoreConfig:
    param_store = None
    shopify_config = None
    newstore_config = None

    def __init__(self, tenant, stage, region):
        self.tenant = tenant
        self.stage = stage
        self.region = region

    def get_param_store(self):
        if not self.param_store:
            self.param_store = ParamStore(self.tenant, self.stage)
        return self.param_store

    def get_shopify_config(self):
        if not self.shopify_config:
            shop_manager = ShopManager(self.tenant, self.stage, self.region)
            self.shopify_config = shop_manager.get_shop_config('frankandoak-shopify-dev-usa')
        return self.shopify_config
