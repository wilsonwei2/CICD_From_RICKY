import base64
import requests
import logging

# import json

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

SHOPIFY_HOST = 'myshopify.com/admin'


class ShopifyConnector:
    """
    This classes handles interaction with shopify
    """
    host = None
    api_key = None
    password = None
    shop = None
    url = None

    def __init__(self, api_key, password, shop=None, url=None, host=SHOPIFY_HOST):  # pylint: disable=too-many-arguments
        self.host = host
        self.api_key = api_key
        self.password = password
        auth_string = ('{key}:{pwd}'.format(
            key=self.api_key, pwd=self.password))
        self.auth_header = {
            'Content-Type': 'application/json ',
            'Authorization': 'Basic {auth_base64}'.format(
                auth_base64=base64.b64encode(auth_string.encode()).decode('utf-8'))
        }
        self.shop = shop
        if not url:
            self.url = 'https://{shop}.{host}'.format(
                shop=shop, host=host)
        else:
            self.url = url

    def get_orders(self, starts_at, ends_at, params, query=None, limit=250):  # pylint: disable=too-many-arguments
        """
        Get shopify order based on a shopify order id;
        params allows to pass a filter of the fields that should be available in the response
        """
        endpoint = '{url}/orders.json'.format(url=self.url)
        next_page = None

        data = {
            'updated_at_min': starts_at,
            'updated_at_max': ends_at,
            'limit': limit
        }

        if params:
            data['fields'] = params

        if query:
            data.update(query)

        orders = []

        while True:  # pylint: disable=R1702
            if next_page:
                next_page_parts = next_page.split('?')
                endpoint = next_page_parts[0]
                data = {}

                if len(next_page_parts) > 1:
                    for next_page_param in next_page_parts[1].split('&'):
                        next_page_param_parts = next_page_param.split('=')
                        data[next_page_param_parts[0]] = next_page_param_parts[1]

            response = requests.get(url=endpoint, headers=self.auth_header, params=data)
            response.raise_for_status()
            body = response.json()

            if 'errors' in body:
                raise Exception(body['errors'])

            if len(body['orders']) > 0:
                orders += body['orders']

            next_page = self._get_next_link(response.headers)

            if not next_page:
                break

        return orders

    def _get_next_link(self, headers):
        links = headers.get('Link', None)

        if links:
            for link in links.split(','):
                if 'rel="next"' in link:
                    return link.split(';')[0].strip()[1:-1]

        return None

    def _refund_data(self, order):
        '''Used for order level discount proration'''
        order_id = order['id']
        items = [{'line_item_id': i['id'], 'quantity': i['quantity']}
                 for i in order['line_items']]
        endpoint = '{url}/orders/{id}/refunds/calculate.json'.format(
            url=self.url, id=order_id)
        data = {
            'refund': {
                'shipping': {
                    'full_refund': True
                },
                'refund_line_items': items
            }
        }
        response = requests.post(
            url=endpoint, headers=self.auth_header, json=data)
        response.raise_for_status()
        return {i['line_item_id']: i for i in response.json()['refund']['refund_line_items']}

    def _transaction_data(self, order):
        '''Get transaction infomation from Shopify'''
        order_id = order['id']
        endpoint = '{url}/orders/{id}/transactions.json'.format(
            url=self.url, id=order_id)
        response = requests.get(url=endpoint, headers=self.auth_header)
        response.raise_for_status()
        return response.json().get('transactions')

    def _get_hook_by_url(self, url):
        query = {
            'address': url
        }
        endpoint = '{url}/webhooks.json'.format(
            url=self.url)
        response = requests.get(
            url=endpoint, headers=self.auth_header, params=query)
        try:
            response.raise_for_status()
        except Exception:
            LOGGER.exception('Failed to get webhook')
            LOGGER.error(response.text)
            raise Exception(response.text)
        LOGGER.info(response.json())
        return response.json().get('webhooks')

    def _create_hook(self, url, event):
        data = {
            "webhook": {
                "topic": event,
                "address": url,
                "format": "json"
            }
        }
        endpoint = '{url}/webhooks.json'.format(
            url=self.url)
        response = requests.post(
            url=endpoint, headers=self.auth_header, json=data)
        try:
            response.raise_for_status()
        except Exception:
            LOGGER.exception('Failed to create webhook')
            LOGGER.error(response.text)
            raise Exception(response.text)
        LOGGER.info(response.json())
        return response.json().get('webhooks')

    def get_order(self, order_id: str, params: dict) -> dict:
        """
        Get shopify order based on a shopify order id;
        params allows to pass a filter of the fields that should be available in the response
        """
        endpoint = f'{self.url}/orders/{order_id}.json'
        LOGGER.info(endpoint)
        response = requests.get(url=endpoint, headers=self.auth_header, params={'fields': params})
        LOGGER.info(response.json())
        try:
            response.raise_for_status()
        except Exception:
            LOGGER.exception('Failed to get order info')
            LOGGER.error(response.text)
            raise Exception(response.text)
        return response.json()['order']
