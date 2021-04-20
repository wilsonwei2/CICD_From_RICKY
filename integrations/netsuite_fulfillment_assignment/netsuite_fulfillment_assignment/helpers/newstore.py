import os
import json
import logging
import requests
from requests import HTTPError
LOGGER = logging.getLogger(__name__)
LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER.setLevel(LOG_LEVEL)


class NShandler():
    host = None
    username = None
    password = None
    token = None

    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password

    def get_token(self):
        if not self.token:
            LOGGER.info(f'Getting token from newstore {self.host}')
            url = f'https://{self.host}/v0/token'
            headers = {
                'Host': self.host
            }
            form = {
                'grant_type': 'password',
                'username': self.username,
                'password': self.password
            }
            response = requests.post(url=url, headers=headers, data=form)
            response.raise_for_status()
            self.token = response.json()
        else:
            LOGGER.info('Token already exists')
        return self.token['access_token']

    def get_headers(self):
        return {
            'Content-Type': 'application/json',
            'tenant': os.environ.get('tenant', 'frankandoak'),
            'Authorization': f'Bearer {self.get_token()}'
        }

    def send_shipment(self, ff_id, response_json):
        url = 'https://%s/v0/d/fulfillment_requests/%s/shipment' % (self.host, ff_id)
        response = requests.post(url, headers=self.get_headers(), json=response_json)
        try:
            response.raise_for_status()
        except HTTPError as ex:
            LOGGER.error(f'Response: {response.text}; \nException: {str(ex)}', exc_info=True)
            raise
        return response.json()

    def get_external_order(self, external_order_id, email=None, country_cod=None, id_type=None):
        if id_type is not None:
            external_order_id = "%s=%s" % (id_type, external_order_id)

        url = 'https://%s/v0/d/external_orders/%s' % (self.host, external_order_id)
        search_params = {}

        if email:
            search_params['email'] = email
        if country_cod:
            search_params['country_code'] = country_cod

        response = requests.get(url, headers=self.get_headers(), params=search_params)

        try:
            response.raise_for_status()
        except HTTPError as ex:
            LOGGER.error(f'Response: {response.text}; \nException: {str(ex)}', exc_info=True)
            raise
        return response.json()

    def get_customer_order(self, order_id):
        url = 'https://%s/v0/c/customer_orders/%s' % (self.host, order_id)
        try:
            response = requests.get(url, headers=self.get_headers())
        except HTTPError as ex:
            LOGGER.error(f'Response: {response.text}; \nException: {str(ex)}', exc_info=True)
            raise
        return response.json()

    def get_order_by_external_id(self, ext_id):
        """
        Get Newstore order based on country_code, zip and email,
        country_code can be empty
        """
        url = f'https://{self.host}/v0/d/external_orders/id={ext_id}'
        LOGGER.info(f'Getting order values from newstore {url}')
        response = requests.get(url=url, headers=self.get_headers())
        response.raise_for_status()
        return response.json()

    def get_order(self, order_id):
        """
        Get Newstore order
        """
        url = f'https://{self.host}/v0/c/orders/{order_id}'
        LOGGER.info(f'Getting order values from newstore {url}')
        response = requests.patch(url=url, headers=self.get_headers(), json={})
        response.raise_for_status()
        return response.json()

    def fulfill_order(self, order_data):
        url = f'https://{self.host}/v0/d/fulfill_order'
        LOGGER.info(f"Sending order {order_data['external_id']} to {url}")
        LOGGER.debug(f"Order: \n{json.dumps(order_data, indent=4)}")

        response = requests.post(url, headers=self.get_headers(), json=order_data)
        try:
            response.raise_for_status()
        except HTTPError as ex:
            LOGGER.error(f'Response: {response.text}; \nException: {str(ex)}', exc_info=True)
            raise
        return response.json()

    def get_in_store_pickup_options(self, request_json):
        """ Retrieve in-store pickup offer tokens based on geo location, items and search radius """
        url = f'https://{self.host}/v0/d/in_store_pickup_options'
        response = requests.post(url, headers=self.get_headers(), json=request_json)
        response.raise_for_status()
        return response.json()

    def get_product(self, sku: str) -> dict:
        product_sku = sku.replace("/", "%2F")
        url = f'https://{self.host}/api/v1/shops/storefront-catalog-en/products/{product_sku}'
        query = {
            'locale': 'en-US'
        }
        response = requests.get(url=url, headers=self.get_headers(), params=query)
        response.raise_for_status()
        return response.json()

    def send_acknowledgement(self, ff_id):
        url = f'https://{self.host}/v0/d/fulfillment_requests/{ff_id}/acknowledgement'

        try:
            response = requests.post(url, headers=self.get_headers(), json={})
        except HTTPError as ex:
            LOGGER.error(f'Response: {response.text}; \nException: {str(ex)}', exc_info=True)
            return False

        return True
