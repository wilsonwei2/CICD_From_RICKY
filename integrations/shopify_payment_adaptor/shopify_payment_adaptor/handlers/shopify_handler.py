import aiohttp
import asyncio
import base64
import logging
import json

from shopify_payment_adaptor.aws.error import raise_error_if_exists

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

    def __init__(self, api_key: str, password: str, shop: str, host: str = SHOPIFY_HOST, url=None):
        self.host = host
        self.api_key = api_key
        self.password = password
        auth_string = ('{key}:{pwd}'.format(
            key=self.api_key, pwd=self.password))
        self.auth_header = {
            'Content-Type': 'application/json ',
            'Authorization': 'Basic {auth_base64}'.format(auth_base64=base64.b64encode(auth_string.encode()).decode('utf-8'))
        }
        self.shop = shop
        if not url:
            self.url = 'https://{shop}.{host}'.format(
                shop=shop, host=host)
        else:
            self.url = url

    async def create_refund(self, order_id: str, data: dict) -> dict:
        """
        Create a refund at shopify
        """
        endpoint = '{url}/orders/{id}/refunds.json'.format(
            url=self.url, id=order_id)
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.post(url=endpoint, headers=self.auth_header, json=data) as response:
                return await raise_error_if_exists(response)

    async def get_refund(self, order_id: str, refund_id: str) -> dict:
        """
        Create a refund at shopify
        """
        endpoint = '{url}/orders/{id}/refunds/{refund_id}.json'.format(
            url=self.url, id=order_id, refund_id=refund_id)
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=endpoint, headers=self.auth_header) as response:
                body = await response.json()
                if 'errors' in body:
                    raise Exception(body['errors'])
                return body

    async def calculate_refund(self, order_id: str, data: dict) -> dict:
        """
        Calculate a refund at shopify
        """
        endpoint = '{url}/orders/{id}/refunds/calculate.json'.format(
            url=self.url, id=order_id)
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.post(url=endpoint, headers=self.auth_header, json=data) as response:
                body = await response.json()
                if 'errors' in body:
                    LOGGER.error(body['errors'])
                    raise Exception(body['errors'])
                response.raise_for_status()
                return body

    async def get_order(self, order_id: str, params: dict) -> dict:
        """
        Get shopify order based on a shopify order id;
        params allows to pass a filter of the fields that should be available in the response
        """
        endpoint = '{url}/orders/{id}.json'.format(
            url=self.url, id=order_id)
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=endpoint, headers=self.auth_header, params={'fields': params}) as response:
                body = await response.json()
                if 'errors' in body:
                    LOGGER.error(body['errors'])
                    raise Exception(body['errors'])
                return body['order']

    async def get_transaction(self, order_id: str, transaction_id: str) -> dict:
        """
        Get shopify order based on a shopify order id;
        params allows to pass a filter of the fields that should be available in the response
        """
        endpoint = '{url}/orders/{id}/transactions/{transaction_id}.json'.format(
            url=self.url, id=order_id, transaction_id=transaction_id)
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=endpoint, headers=self.auth_header) as response:
                body = await response.json()
                if 'errors' in body:
                    LOGGER.error(body['errors'])
                    raise Exception(body['errors'])
                return body['transaction']

    async def get_transactions_for_order(self, shopify_order_id: str) -> dict:
        """
        Get shopify transactions associated with a shopify order;
        params allows to pass a filter of the fields that should be available in the response
        """
        endpoint = '{url}/orders/{id}/transactions.json'.format(
            url=self.url, id=shopify_order_id)
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=endpoint, headers=self.auth_header) as response:
                body = await response.json()
                if 'errors' in body:
                    LOGGER.error(body['errors'])
                    raise Exception(body['errors'])
                return body['transactions']

    async def create_fulfillment(self, order_id, data):
        """
        Create a fullfilment at shopify
        """
        endpoint = '{url}/orders/{id}/fulfillments.json'.format(
            url=self.url, id=order_id)
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.post(url=endpoint, headers=self.auth_header, json=data) as response:
                body = await response.json()
                raise_for_status = True
                if 'errors' in body:
                    # Only raise if error is not of already fulfilled
                    if 'base' in body['errors'] and 'already' in body['errors']['base'][0]:
                        raise_for_status = False
                    else:
                        raise Exception(body['errors'])
                if raise_for_status:
                    response.raise_for_status()
                return body

    async def create_transaction(self, order_id: str, data: dict) -> dict:
        """
        Creates a order transaction at shopify (capture, auth)
        """
        endpoint = '{url}/orders/{id}/transactions.json'.format(
            url=self.url, id=order_id)
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.post(url=endpoint, headers=self.auth_header, json=data) as response:
                body = await response.json()
                if 'errors' in body:
                    raise Exception(body['errors'])
                response.raise_for_status()
                return body

    async def active_gift_card(self, customer_id: str, amount: float, currency: str, **kwargs) -> dict:
        """
        Creates a gift card at shopify
        """
        LOGGER.info(f'In activate Gift Card, Customer ID Number is -- {customer_id}')
        endpoint = '{url}/gift_cards.json'.format(
            url=self.url)
        payload = {
            'gift_card': {
                'initial_value': amount,
                'currency': currency.upper(),
                'customer_id': customer_id
            }
        }
        LOGGER.info(payload)
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.post(url=endpoint, headers=self.auth_header, json=payload) as response:
                body = await response.json()
                if 'errors' in body:
                    raise Exception(body['errors'])
                response.raise_for_status()
                return body

    async def search_gift_card(self, find_by_value: str) -> dict:
        """
        Creates a gift card at shopify
        """
        LOGGER.info(f'In Search Gift Card, Shopify Gift Card Number is -- {find_by_value}')
        endpoint = '{url}/gift_cards/search.json'.format(
            url=self.url)
        parameters = {'query': find_by_value}
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=endpoint, headers=self.auth_header, params=parameters) as response:
                body = await response.json()
                if 'errors' in body:
                    raise Exception(body['errors'])
                response.raise_for_status()
                return body

    async def adjust_gift_card(self, gift_card_number: str, capture_amount: float, reason: str = '') -> dict:
        """
        Adjust gift card at  value at shopify, collect or add money
        """
        LOGGER.info(f'In Adjust Gift Card, Shopify Gift Card Number is -- {gift_card_number}')
        endpoint = '{url}/gift_cards/{gift_card}/adjustments.json'.format(
            url=self.url, gift_card=gift_card_number)
        payload = {
            'adjustment': {
                'amount': capture_amount,
                'note': reason
            }
        }

        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.post(url=endpoint, headers=self.auth_header, json=payload) as response:
                body = await response.json()
                if 'errors' in body:
                    raise Exception(body['errors'])
                response.raise_for_status()
                return body

    async def void_transaction(self, order_id: str, amount: str, auth_id: str = None) -> dict:
        endpoint = '{url}/orders/{order_id}/transactions.json'.format(
            url=self.url, order_id=order_id)
        request = {
            'transaction': {
                'kind': 'void',
                'amount': str(amount)
            }
        }
        if auth_id:
            request['transaction']['parent_id'] = str(auth_id)
        LOGGER.info(f'Requesting to void: ${json.dumps(request)}', )
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.post(url=endpoint, headers=self.auth_header, json=request) as response:
                if response.status >= 500:
                    raise Exception(f'Error connecting to shopify: {response.status}')
                body = await response.json()
                if response.status in [404, 422, 409]:
                    return {}
                if body and 'errors' in body:
                    if 'base' in body['errors'] and 'already' in body['errors']['base'][0]:
                        LOGGER.info(
                            f'Already Voided transaction: ${json.dumps(body)}')
                        return {}
                    raise Exception(body['errors'])
                response.raise_for_status()
                return body

    async def cancel_order(self, order_id: str) -> dict:
        endpoint = '{url}/orders/{order_id}/cancel.json?email=true'.format(
            url=self.url, order_id=order_id)
        LOGGER.info(f'endpoint: {endpoint}')
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.post(url=endpoint, headers=self.auth_header) as response:
                body = await response.json()
                if response.status in [409, 422]:
                    return {}
                if body and 'errors' in body:
                    if 'base' in body['errors'] and 'already' in body['errors']['base'][0]:
                        LOGGER.info(
                            f'Alreeady Cancelled transaction: ${json.dumps(body)}')
                        return {}
                    raise Exception(body['errors'])
                response.raise_for_status()
                return body

    async def search_customer_by_email(self, email: str) -> dict:
        """
        Search for a customer at shopify
        """
        endpoint = '{url}/customers/search.json'.format(
            url=self.url)
        parameters = {
            'query': 'email:${email}'.format(email=email),
            'fields': 'id'
        }
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=endpoint, headers=self.auth_header, params=parameters) as response:
                body = await response.json()
                if body and 'errors' in body:
                    raise Exception(body['errors'])
                response.raise_for_status()
                return body

    async def create_customer(self, email: str, name: str = None) -> dict:
        """
        Creates a customer at shopify
        """
        endpoint = '{url}/customers.json'.format(
            url=self.url)
        customer = {
            'customer': {
                'email': email
            }
        }
        if name:
            customer['customer']['name'] = name
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.post(url=endpoint, headers=self.auth_header, json=customer) as response:
                body = await response.json()
                if body and 'errors' in body:
                    raise Exception(body['errors'])
                response.raise_for_status()
                return body

    async def get_variant_metafields(self, product_id: str, variant_id: str, params: dict) -> dict:
        """
        Get shopify variant metafields;
        params allows to pass a filter of the fields that should be available in the response
        """
        endpoint = '{url}/products/{product_id}/variants/{variant_id}/metafields.json'.format(
            url=self.url, product_id=product_id, variant_id=variant_id)
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=endpoint, headers=self.auth_header, params=params) as response:
                body = await response.json()
                if body and 'errors' in body:
                    raise Exception(body['errors'])
                return body['metafields']
