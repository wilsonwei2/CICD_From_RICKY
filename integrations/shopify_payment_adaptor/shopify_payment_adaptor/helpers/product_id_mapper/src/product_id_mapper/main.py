import logging
import os
import requests
from requests.utils import quote


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

TENANT = os.environ.get('TENANT', 'frankandoak')
STAGE = os.environ.get('STAGE', 'x')


def _map_product_ext_identifiers(external_identifiers: list):
    return_dict = {}
    for identifier in external_identifiers:
        if 'key' in identifier and 'value' in identifier:
            return_dict[identifier['type']] = identifier['value']
    return return_dict


class ProductIdMapper():
    """
    fetch identifiers for products.
    """

    def __init__(self):
        self.tenant = TENANT
        self.stage = STAGE
        self.host = f'{self.tenant}.{self.stage}.newstore.net'

    def find(self, key, value, shop='storefront-catalog-en', locale='en-US', params=None):
        """
        Get the product by identifier type from the consumer API
        https://<host>/api/v1/shops/storefront-catalog-en/products/sku=AB30-064-15-?locale=en-US
        :param ctx: The context containing the url and auth
        :param key: key to look for
        :param value: value of the key
        :param params: the params to pass in the call
        :return: the json parsed response
        """
        value = quote(value, safe='')
        url = f'https://{self.host}/api/v1/shops/{shop}/products'
        params = {}
        params[key] = value
        if locale:
            params['locale'] = locale

        response = requests.get(url, params=params)
        try:
            response.raise_for_status()
        except Exception:
            LOGGER.exception('Could not find product map')
            return None
        return response.json()

    def get_map(self, key, value):
        product_mapped = {}
        id_map = self.find(key, value)

        if id_map:
            external_identifiers = id_map.get('external_identifiers', [])
            product_mapped = _map_product_ext_identifiers(external_identifiers)
            product_mapped['product_id'] = id_map.get('product_id')
            product_mapped['is_active'] = id_map.get('is_active')
        LOGGER.info(f'GET Product ID Map = {product_mapped}')
        return product_mapped
