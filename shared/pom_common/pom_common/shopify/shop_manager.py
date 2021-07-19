"""
Module shop_manager.py
"""
from pom_common.aws.secrets_manager import get_secret_value
import boto3
import json
import logging

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class InvalidShopId(Exception):
    pass


def get_shopify_param(tenant, stage):
    path = f'/{tenant}/{stage}/shopify'
    try:
        ssm_client = boto3.client('ssm')
        response = ssm_client.get_parameter(
            Name=path, WithDecryption=False)
        return json.loads(response['Parameter']['Value'])
    except Exception:
        LOGGER.exception(f'Error when trying to get parameter {path}')
        return None

class ShopManager:
    shop_ids = []
    configs = {}


    def __init__(self, tenant, stage, region):
        self.region = region
        self.shop_ids = get_shopify_param(tenant, stage)['shop_ids']


    def get_shop_ids(self):
        return self.shop_ids


    def get_shop_config(self, shop_id):
        if shop_id in self.shop_ids:
            if not shop_id in self.configs:
                self.configs[shop_id] = json.loads(get_secret_value(shop_id, self.region))
            return self.configs[shop_id]

        raise InvalidShopId
