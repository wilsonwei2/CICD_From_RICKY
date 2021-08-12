import base64
import requests
import logging
import json

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


    def __init__(self, api_key, password, shop, url=None, host=SHOPIFY_HOST):
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
        self.graphql_url = f'https://{shop}.{host}/api/2021-04/graphql.json'
        if not url:
            self.url = 'https://{shop}.{host}'.format(
                shop=shop, host=host)
        else:
            if url[-6:] == '/admin':
                self.url = url
            else:
                self.url = '{url}/admin'.format(url=url)

    def get_shop(self):
        return self.shop

    def get_product_count(self, params={}):
        endpoint = '{url}/products/count.json'.format(
            url=self.url)
        response = requests.get(url=endpoint, headers=self.auth_header, params=params)
        response.raise_for_status()
        return response.json().get('count', 0)

    def get_products_cursor(self, params, next_page=None):
        if next_page:
            endpoint = next_page
        else:
            endpoint = f'{self.url}/products.json'

        try:
            if next_page:
                r = requests.get(url=endpoint, headers=self.auth_header)
            else:
                r = requests.get(url=endpoint, headers=self.auth_header, params=params)

        except Exception as e:
            LOGGER.error('Error while trying to get product list: %s', str(e))
            return None

        response_json = r.json()

        LOGGER.info(json.dumps(response_json['products'], indent=4))
        LOGGER.info(f'Headers: {r.headers}')

        links = r.headers.get('Link', '').split(',')
        next_page = ''
        last_page = ''
        for link in links:
            if link and len(link.split(';')) > 1:
                if 'previous' in link.split(';')[1]:
                    last_page = link.split(';')[0].strip()[1:-1]
                elif 'next' in link.split(';')[1]:
                    next_page = link.split(';')[0].strip()[1:-1]

        return response_json['products'], last_page, next_page

    def get_products(self, page, params={}):
        endpoint = '{url}/products.json'.format(
            url=self.url)
        params['page'] = page
        response = requests.get(url=endpoint, headers=self.auth_header, params=params)
        response.raise_for_status()
        return response.json().get('products', {})


    def get_variant(self, product_id, variant_id, params={}):
        endpoint = '{url}/products/{product_id}/variants/{variant_id}.json'.format(
            url=self.url, product_id=product_id, variant_id=variant_id)
        response = requests.get(url=endpoint, headers=self.auth_header, params=params)
        try:
            response.raise_for_status()
        except Exception:
            LOGGER.exception('Could not find variant')
            return None
        return response.json().get('variant', {})


    def get_gift_card(self, number):
        endpoint = '{url}/gift_cards/{number}.json'.format(
            url=self.url, number=number)
        response = requests.get(url=endpoint, headers=self.auth_header)
        response.raise_for_status()
        return response.json().get('gift_card',{})

    def get_orders(self, starts_at, ends_at, params,
                    limit=250, page=1, status='any', financial_status='any',
                    ids=[]):
        endpoint = '{url}/orders.json'.format(
            url=self.url)
        data = {
            'updated_at_min': starts_at,
            'updated_at_max': ends_at,
            'limit': limit,
            'status': status,
            'financial_status': financial_status
        }

        if starts_at or ends_at:
            data['created_at_min'] = starts_at
            data['created_at_max'] = ends_at

        if params:
            data['fields'] = params

        if ids:
            data['ids'] = ','.join(ids)

        orders = []
        next_page = ''
        while True:
            endpoint = next_page if next_page else endpoint
            response = requests.get(
                url=endpoint, headers=self.auth_header, params=data)
            response.raise_for_status()
            body = response.json()
            if 'errors' in body:
                raise Exception(body['errors'])
            elif len(body['orders']) > 0:
                orders += body['orders']

            # Get next page from headers returned by Shopify
            next_page = ''
            links = response.headers.get('Link', '').split(',')
            for link in links:
                link_parts = link.split(';')
                if link and len(link_parts) > 1:
                    if 'next' in link_parts[1]:
                        next_page = link_parts[0].strip()[1:-1]

            # Break loop if there's no next page to call
            if not next_page:
                break

        return orders

    def get_historical_orders(self, starts_at, ends_at, params, status='any', limit=250, page=1,
                              timestamp_type='created_at'):
        """
        Get shopify order based on a timestamp;
        params allows to pass a filter of the fields that should be available in the response
        """
        endpoint = '{url}/orders.json'.format(
            url=self.url)
        data = {
            'limit': limit,
            'status': status,
            'page': page
        }
        min_time = 'created_at_min'
        max_time = 'created_at_max'
        data[min_time] = starts_at
        data[max_time] = ends_at
        if params:
            data['fields'] = params
        orders = []
        while True:
            LOGGER.info('Getting orders for: %s', json.dumps(data))
            response = requests.get(
                url=endpoint, headers=self.auth_header, params=data)
            response.raise_for_status()
            body = response.json()
            if 'errors' in body:
                raise Exception(body['errors'])
            elif len(body['orders']) > 0:
                orders += body['orders']
                data['page'] += 1
            else:
                return orders
        return orders

    def get_order(self, order_id, fields=None):
        """
        Get shopify order based on a shopify order id;
        fields filter of the fields that should be available in the response
        """
        endpoint = '{url}/orders/{id}.json'.format(
            url=self.url, id=order_id)
        data = {}
        if fields:
            data['fields'] = fields
        response = requests.get(url=endpoint, headers=self.auth_header, params=data)
        response.raise_for_status()
        return response.json().get('order',{})


    def get_order_by_name(self, order_name, status='any'):
        """
        Get shopify order based on a shopify order id;
        fields filter of the fields that should be available in the response
        """
        endpoint = '{url}/orders.json'.format(url=self.url)
        data = {
            'name': order_name,
            'status': status
        }
        response = requests.get(url=endpoint, headers=self.auth_header, params=data)
        response.raise_for_status()
        orders = response.json().get('orders', [])
        for order in orders:
            if order.get('name', '').replace('#', '') == order_name:
                return order
        return None


    def create_order(self, order_data):
        '''Create Order in Shopify'''
        endpoint = '{url}/orders.json'.format(url=self.url)
        response = requests.post(
            url=endpoint, headers=self.auth_header, json=order_data)
        body = response.json()
        if 'errors' in body:
            raise Exception(body['errors'])
        return body


    def update_order(self, order_id, order_data):
        '''Updates the existing order with data provided -- it could be with multiple tags as well.'''
        endpoint = '{url}/orders/{order_id}.json'.format(url=self.url, order_id=order_id)
        response = requests.put(
            url=endpoint, headers=self.auth_header, json=order_data)
        body = response.json()
        if 'errors' in body:
            raise Exception(body['errors'])
        return body

    def order_tags_add(self, order_id, tags=[]):
        query = '''
        mutation tagsAdd($id: ID!, $tags: [String!]!) {
            tagsAdd(id: $id, tags: $tags) {
                node {
                    id
                }
                userErrors {
                    field
                    message
                }
            }
        }
        '''

        return self.__graphql_post__(query, {
            'id': f'gid://shopify/Order/{order_id}',
            'tags': tags
        })

    def order_tags_remove(self, order_id, tags=[]):
        query = '''
        mutation tagsRemove($id: ID!, $tags: [String!]!) {
            tagsRemove(id: $id, tags: $tags) {
                node {
                    id
                }
                userErrors {
                    field
                    message
                }
            }
        }
        '''

        return self.__graphql_post__(query, {
            'id': f'gid://shopify/Order/{order_id}',
            'tags': tags
        })

    def refund_data(self, order):
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


    def transaction_data(self, order):
        '''Get transaction infomation from Shopify'''
        order_id = order['id']
        endpoint = '{url}/orders/{id}/transactions.json'.format(
            url=self.url, id=order_id)
        response = requests.get(url=endpoint, headers=self.auth_header)
        response.raise_for_status()
        return response.json().get('transactions')


    def get_metafields(self, product_id, variant_id, params=None):
        '''Get metafield infomation for a Shopify product variant'''
        endpoint = '{url}/products/{product_id}/variants/{variant_id}/metafields.json'.format(
            url=self.url, product_id=product_id, variant_id=variant_id)
        if not 'limit' in params:
            params['limit'] = 250
        response = requests.get(url=endpoint, headers=self.auth_header, params=params)
        try:
            response.raise_for_status()
        except Exception:
            return None
        return response.json().get('metafields')


    def get_order_risks(self, order_id):
        endpoint = '{url}/orders/{order_id}/risks.json'.format(
            url=self.url, order_id=order_id)
        response = requests.get(url=endpoint, headers=self.auth_header)
        response.raise_for_status()
        return response.json().get('risks')


    def get_fulfillments(self, order_id, params=None):
        '''Get fulfillments for a Shopify order'''
        endpoint = '{url}/orders/{order_id}/fulfillments.json'.format(
            url=self.url, order_id=order_id)
        response = requests.get(url=endpoint, headers=self.auth_header, params=params)
        response.raise_for_status()
        return response.json().get('fulfillments')


    def create_fulfillment(self, order_id, json_data, return_response=False):
        '''Create Fulfillment for Shopify order'''
        endpoint = '{url}/orders/{order_id}/fulfillments.json'.format(
            url=self.url, order_id=order_id)
        response = requests.post(
            url=endpoint, headers=self.auth_header, json=json_data)
        if return_response:
            return response.json()

        body = response.json()
        if 'errors' in body:
            raise Exception(body['errors'])
        if 'error' in body:
            raise Exception(body['error'])

        response.raise_for_status()
        return response.ok


    def count_fulfillments(self, order_id, params=None):
        '''Get fulfillment count for a Shopify order'''
        endpoint = '{url}/orders/{order_id}/fulfillments/count.json'.format(
            url=self.url, order_id=order_id)
        response = requests.get(url=endpoint, headers=self.auth_header, params=params)
        response.raise_for_status()
        return response.json().get('count')


    def create_refund(self, order_id, data):
        """
        Create a refund at shopify
        """
        endpoint = '{url}/orders/{id}/refunds.json'.format(
            url=self.url, id=order_id)
        response = requests.post(
            url=endpoint, headers=self.auth_header, json=data)
        response.raise_for_status()
        return response.json()

    def get_refunds(self, order_id):
        """
        Retrieve order refunds from shopify
        """
        endpoint = '{url}/orders/{id}/refunds.json'.format(
            url=self.url, id=order_id)
        response = requests.get(
            url=endpoint, headers=self.auth_header)
        response.raise_for_status()
        return response.json()

    def calculate_refund(self, order_id, data):
        """
        Calculate a refund at shopify
        """
        endpoint = '{url}/orders/{id}/refunds/calculate.json'.format(
            url=self.url, id=order_id)
        response = requests.post(
            url=endpoint, headers=self.auth_header, json=data)
        response.raise_for_status()
        return response.json()


    def create_transaction(self, order_id, data):
        """
        Creates a order transaction at shopify (capture, auth)
        """
        endpoint = '{url}/orders/{id}/transactions.json'.format(
            url=self.url, id=order_id)
        response = requests.post(
            url=endpoint, headers=self.auth_header, json=data)
        response.raise_for_status()
        return response.json()


    def search_customer_by_email(self, email):
        """
        Search for a customer at shopify
        """
        endpoint = '{url}/customers/search.json'.format(
            url=self.url)
        parameters = {
            'query': 'email:${email}'.format(email=email),
            'fields': 'id,email'
        }
        response = requests.get(url=endpoint, headers=self.auth_header, params=parameters)
        response.raise_for_status()
        return response.json()


    def create_customer(self, email, first_name=None, last_name=None):
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

        if first_name:
            customer['customer']['first_name'] = first_name
        if last_name:
            customer['customer']['last_name'] = last_name

        LOGGER.info("Create customer: \n%s" % json.dumps(customer, indent=4))

        response = requests.post(
            url=endpoint, headers=self.auth_header, json=customer)

        body = response.json()
        if 'errors' in body:
            raise Exception(body['errors'])

        response.raise_for_status()
        return body


    def update_customer(self, customer_id, customer):
        """
        Updates a customer at shopify
        """
        endpoint = '{url}/customers/{id}.json'.format(
            url=self.url, id=customer_id)

        response = requests.put(
            url=endpoint, headers=self.auth_header, json=customer)

        body = response.json()
        if 'errors' in body:
            raise Exception(body['errors'])

        response.raise_for_status()
        return body


    def get_transactions(self, order_id, fields):
        """
        Get shopify order transactions based on a shopify order id;
        params allows to pass a filter of the fields that should be available in the response
        """
        endpoint = '{url}/orders/{id}/transactions.json'.format(
            url=self.url, id=order_id)
        data = {}
        if fields:
            data['fields'] = fields
        response = requests.get(url=endpoint, headers=self.auth_header, params=data)
        response.raise_for_status()
        return response.json().get('transactions',{})


    def void_transaction(self, order_id):
        endpoint = '{url}/orders/{order_id}/transactions.json'.format(
            url=self.url, order_id=order_id)
        body = {"transaction": {"kind": "void"}}
        response = requests.post(url=endpoint, headers=self.auth_header, json=body)
        response.raise_for_status()
        return response.json()


    def cancel_order(self, order_id):
        endpoint = '{url}/orders/{order_id}/cancel.json'.format(
            url=self.url, order_id=order_id)
        response = requests.post(url=endpoint, headers=self.auth_header)
        response.raise_for_status()
        return response.json()


    def active_gift_card(self, customer_id, amount, currency, **kwargs):
        """
        Creates a gift card at shopify
        """
        endpoint = '{url}/gift_cards.json'.format(
            url=self.url)
        payload = {
            'gift_card': {
                'initial_value': amount,
                'currency': currency.upper(),
                'customer_id': customer_id
            }
        }
        response = requests.post(url=endpoint, headers=self.auth_header, json=payload)
        response.raise_for_status()
        return response.json()


    def search_gift_card(self, find_by_value):
        """
        Creates a gift card at shopify
        """
        endpoint = '{url}/gift_cards/search.json'.format(
            url=self.url)
        parameters = {'query': find_by_value}
        response = requests.get(url=endpoint, headers=self.auth_header, params=parameters)
        response.raise_for_status()
        return response.json()


    def adjust_gift_card(self, gift_card_number, capture_amount, reason=''):
        """
        Adjust gift card at  value at shopify, collect or add money
        """
        endpoint = '{url}/gift_cards/{gift_card}/adjustments.json'.format(
            url=self.url, gift_card=gift_card_number)
        payload = {
            'adjustment': {
                'amount': capture_amount,
                'note': reason
            }
        }
        response = requests.post(url=endpoint, headers=self.auth_header, json=payload)
        response.raise_for_status()
        return response.json()


    def get_locations(self, params={}):
        """
        Gets the Locations from Shopify
        """
        endpoint = '{url}/locations.json'.format(url=self.url)
        response = requests.get(url=endpoint, headers=self.auth_header, params=params)
        response.raise_for_status()
        return response.json().get('locations', [])


    def get_inventory_levels(self, location_id, params={}):
        """
        Get the inventory level for a given location
        """
        endpoint = '{url}/locations/{location_id}/inventory_levels.json'.format(
            url=self.url, location_id=location_id)
        if not 'limit' in params:
            params['limit'] = 250
        page = 1
        inventory_levels = []
        while True:
            params['page'] = page
            response = requests.get(
                url=endpoint, headers=self.auth_header, params=params)
            body = response.json()
            if 'errors' in body:
                raise Exception(body['errors'])
            elif len(body['inventory_levels']) > 0:
                inventory_levels += body['inventory_levels']
                page += 1
            else:
                return inventory_levels
        return inventory_levels

    def get_webhooks(self, params={}):
        """
        Gets the Event Webhooks from Shopify
        """
        endpoint = '{url}/webhooks.json'.format(url=self.url)
        response = requests.get(url=endpoint, headers=self.auth_header, params=params)
        response.raise_for_status()
        return response.json().get('webhooks', [])

    def create_hook(self, url, event):
        data = {
            'webhook': {
                'topic': event,
                'address': url,
                'format': 'json'
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

    def get_hook_by_url(self, url, topic=None):
        query = {
            'address': url
        }
        if topic:
            query['topic'] = topic
        endpoint = f'{self.url}/webhooks.json'
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

    def __graphql_post__(self, query, variables={}):
        response = requests.post(self.graphql_url, headers=self.auth_header, json={
            'query': query,
            'variables': variables
        })

        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            LOGGER.exception(error)
            raise error

        return response.json()
