from shopify_import_products.shopify.graphql.queries import START_BULK_OPERATIONS, POLL_OPERATION_STATUS
from shopify_import_products.shopify.param_store_config import ParamStoreConfig
import logging
import requests
import os

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

TENANT = os.environ.get('TENANT') or 'frankandoak'
STAGE = os.environ.get('STAGE') or 'x'
CONFIG = ParamStoreConfig(TENANT, STAGE).get_shopify_config()


class ShopifyAPI:
    def __init__(self):
        shop = CONFIG['shop']
        self.url = f'https://{shop}.myshopify.com/admin/api/2021-04/graphql.json'
        self.auth_token = CONFIG['password']
        self.products_url = None


    def start_bulk_operation(self):
        response_json = self.post_graphql(START_BULK_OPERATIONS)
        return response_json['data']['bulkOperationRunQuery']['bulkOperation']['status'] == 'CREATED'


    def current_bulk_operation(self):
        response_json = self.post_graphql(POLL_OPERATION_STATUS)
        self.products_url = response_json['data']['currentBulkOperation']['url']
        return response_json['data']['currentBulkOperation']['status']


    def get_products_text(self):
        if self.products_url:
            response = requests.get(self.products_url)

            try:
                response.raise_for_status()
            except requests.HTTPError as error:
                LOGGER.exception(response.text)
                LOGGER.exception(error)
                raise error

            return response.text

        return None


    def post_graphql(self, graphql_query):
        LOGGER.info(f'Request: POST {self.url}\n{graphql_query}')
        response = requests.post(self.url, data=graphql_query, headers={
            'Content-Type': 'application/graphql',
            'X-Shopify-Access-Token': self.auth_token
        })

        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            LOGGER.exception(response.text)
            LOGGER.exception(error)
            raise error

        response_json = response.json()
        LOGGER.info(f'Response Header: {response.headers}')

        return response_json
