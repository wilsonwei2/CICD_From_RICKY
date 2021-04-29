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

    def __init__(self, api_key, password, shop=None, url=None, host=SHOPIFY_HOST): # pylint: disable=too-many-arguments
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

    def get_orders(self, starts_at, ends_at, params, query=None, limit=250, page=1): # pylint: disable=too-many-arguments
        """
        Get shopify order based on a shopify order id;
        params allows to pass a filter of the fields that should be available in the response
        """
        endpoint = '{url}/orders.json'.format(
            url=self.url)
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
        while True:
            data['page'] = page
            response = requests.get(
                url=endpoint, headers=self.auth_header, params=data)
            response.raise_for_status()
            body = response.json()
            if 'errors' in body:
                raise Exception(body['errors'])

            if len(body['orders']) > 0:
                orders += body['orders']
                page += 1
            else:
                return orders
        return orders

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
        response = requests.get(url=endpoint, headers=self.auth_header, params={'fields': params})
        try:
            response.raise_for_status()
        except Exception:
            LOGGER.exception('Failed to get order info')
            LOGGER.error(response.text)
            raise Exception(response.text)
        LOGGER.info(response.text)
        return response.json()['order']

### added for testing purpose if connection to shopify is not given
# def _getmockorder():
#     mockorder = '{\"id\":1722069188705,\"email\":\"akasturi@test.com\",\"closed_at\":null,\"created_at\":\"2019-10-07T10:55:19-04:00\",\"updated_at\":\"2019-10-07T10:55:23-04:00\",\"number\":66,\"note\":\"\",\"token\":\"4a2c3cbf3e4016d7421aa5ce3e36bd52\",\"gateway\":\"shopify_payments\",\"test\":true,\"total_price\":\"46.08\",\"subtotal_price\":\"15.00\",\"total_weight\":9,\"total_tax\":\"0.00\",\"taxes_included\":false,\"currency\":\"USD\",\"financial_status\":\"authorized\",\"confirmed\":true,\"total_discounts\":\"0.00\",\"total_line_items_price\":\"15.00\",\"cart_token\":\"\",\"buyer_accepts_marketing\":false,\"name\":\"#1066\",\"referring_site\":null,\"landing_site\":null,\"cancelled_at\":null,\"cancel_reason\":null,\"total_price_usd\":\"46.08\",\"checkout_token\":\"f8d2b43d056f38fb6ed77804b60aec46\",\"reference\":null,\"user_id\":36479238241,\"location_id\":null,\"source_identifier\":null,\"source_url\":null,\"processed_at\":\"2019-10-07T10:55:18-04:00\",\"device_id\":null,\"phone\":null,\"customer_locale\":null,\"app_id\":1354745,\"browser_ip\":\"73.4.224.13\",\"landing_site_ref\":null,\"order_number\":1066,\"discount_applications\":[],\"discount_codes\":[],\"note_attributes\":[{\"name\":\"Kount Risk Assessment\",\"value\":\"Kount has performed a Risk Analysis on this order with the following result: [Review]\"}],\"payment_gateway_names\":[\"shopify_payments\"],\"processing_method\":\"direct\",\"checkout_id\":11347260047457,\"source_name\":\"shopify_draft_order\",\"fulfillment_status\":null,\"tax_lines\":[],\"tags\":\"\",\"contact_email\":\"akasturi@test.com\",\"order_status_url\":\"https:\/\/goorin-bros-staging.myshopify.com\/9724002401\/orders\/4a2c3cbf3e4016d7421aa5ce3e36bd52\/authenticate?key=e04211a7f26f8bfe3a489bbfdaa22b85\",\"presentment_currency\":\"USD\",\"total_line_items_price_set\":{\"shop_money\":{\"amount\":\"15.00\",\"currency_code\":\"USD\"},\"presentment_money\":{\"amount\":\"15.00\",\"currency_code\":\"USD\"}},\"total_discounts_set\":{\"shop_money\":{\"amount\":\"0.00\",\"currency_code\":\"USD\"},\"presentment_money\":{\"amount\":\"0.00\",\"currency_code\":\"USD\"}},\"total_shipping_price_set\":{\"shop_money\":{\"amount\":\"31.08\",\"currency_code\":\"USD\"},\"presentment_money\":{\"amount\":\"31.08\",\"currency_code\":\"USD\"}},\"subtotal_price_set\":{\"shop_money\":{\"amount\":\"15.00\",\"currency_code\":\"USD\"},\"presentment_money\":{\"amount\":\"15.00\",\"currency_code\":\"USD\"}},\"total_price_set\":{\"shop_money\":{\"amount\":\"46.08\",\"currency_code\":\"USD\"},\"presentment_money\":{\"amount\":\"46.08\",\"currency_code\":\"USD\"}},\"total_tax_set\":{\"shop_money\":{\"amount\":\"0.00\",\"currency_code\":\"USD\"},\"presentment_money\":{\"amount\":\"0.00\",\"currency_code\":\"USD\"}},\"total_tip_received\":\"0.0\",\"admin_graphql_api_id\":\"gid:\/\/shopify\/Order\/1722069188705\",\"line_items\":[{\"id\":3818023256161,\"variant_id\":29066397941857,\"title\":\"Indy Pin\",\"quantity\":1,\"sku\":\"123-0077-BRO-O\/S\",\"variant_title\":\"Brown \/ One Size\",\"vendor\":\"Goorin Bros\",\"fulfillment_service\":\"manual\",\"product_id\":3828274233441,\"requires_shipping\":true,\"taxable\":true,\"gift_card\":false,\"name\":\"Indy Pin - Brown \/ One Size\",\"variant_inventory_management\":\"shopify\",\"properties\":[],\"product_exists\":true,\"fulfillable_quantity\":1,\"grams\":9,\"price\":\"15.00\",\"total_discount\":\"0.00\",\"fulfillment_status\":null,\"pre_tax_price\":\"15.00\",\"price_set\":{\"shop_money\":{\"amount\":\"15.00\",\"currency_code\":\"USD\"},\"presentment_money\":{\"amount\":\"15.00\",\"currency_code\":\"USD\"}},\"pre_tax_price_set\":{\"shop_money\":{\"amount\":\"15.00\",\"currency_code\":\"USD\"},\"presentment_money\":{\"amount\":\"15.00\",\"currency_code\":\"USD\"}},\"total_discount_set\":{\"shop_money\":{\"amount\":\"0.00\",\"currency_code\":\"USD\"},\"presentment_money\":{\"amount\":\"0.00\",\"currency_code\":\"USD\"}},\"discount_allocations\":[],\"admin_graphql_api_id\":\"gid:\/\/shopify\/LineItem\/3818023256161\",\"tax_lines\":[],\"origin_location\":{\"id\":1539576299617,\"country_code\":\"US\",\"province_code\":\"CA\",\"name\":\"goorin-bros-staging\",\"address1\":\"1890 Bryant St #208\",\"address2\":\"\",\"city\":\"San Francisco\",\"zip\":\"94110\"},\"destination_location\":{\"id\":1548396691553,\"country_code\":\"US\",\"province_code\":\"MA\",\"name\":\"Aditya Kasturi\",\"address1\":\"Floor - 9\",\"address2\":\"60 South St,\",\"city\":\"Boston\",\"zip\":\"02111\"}}],\"shipping_lines\":[{\"id\":1394336759905,\"title\":\"Priority Mail Express\",\"price\":\"31.08\",\"code\":\"PriorityExpress\",\"source\":\"usps\",\"phone\":null,\"requested_fulfillment_service_id\":null,\"delivery_category\":null,\"carrier_identifier\":null,\"discounted_price\":\"31.08\",\"price_set\":{\"shop_money\":{\"amount\":\"31.08\",\"currency_code\":\"USD\"},\"presentment_money\":{\"amount\":\"31.08\",\"currency_code\":\"USD\"}},\"discounted_price_set\":{\"shop_money\":{\"amount\":\"31.08\",\"currency_code\":\"USD\"},\"presentment_money\":{\"amount\":\"31.08\",\"currency_code\":\"USD\"}},\"discount_allocations\":[],\"tax_lines\":[]}],\"billing_address\":{\"first_name\":\"Aditya\",\"address1\":\"Floor - 9\",\"phone\":\"6148068041\",\"city\":\"Boston\",\"zip\":\"02111\",\"province\":\"Massachusetts\",\"country\":\"United States\",\"last_name\":\"Kasturi\",\"address2\":\"60 South St,\",\"company\":\"New Store \",\"latitude\":null,\"longitude\":null,\"name\":\"Aditya Kasturi\",\"country_code\":\"US\",\"province_code\":\"MA\"},\"shipping_address\":{\"first_name\":\"Aditya\",\"address1\":\"Floor - 9\",\"phone\":\"6148068041\",\"city\":\"Boston\",\"zip\":\"02111\",\"province\":\"Massachusetts\",\"country\":\"United States\",\"last_name\":\"Kasturi\",\"address2\":\"60 South St,\",\"company\":\"New Store \",\"latitude\":null,\"longitude\":null,\"name\":\"Aditya Kasturi\",\"country_code\":\"US\",\"province_code\":\"MA\"},\"fulfillments\":[],\"client_details\":{\"browser_ip\":\"73.4.224.13\",\"accept_language\":\"en-US,en;q=0.9\",\"user_agent\":\"Mozilla\/5.0 (Macintosh; Intel Mac OS X 10_14_3) AppleWebKit\/537.36 (KHTML, like Gecko) Chrome\/77.0.3865.90 Safari\/537.36\",\"session_hash\":null,\"browser_width\":null,\"browser_height\":null},\"refunds\":[],\"payment_details\":{\"credit_card_bin\":\"424242\",\"avs_result_code\":\"Y\",\"cvv_result_code\":\"M\",\"credit_card_number\":\"\u2022\u2022\u2022\u2022 \u2022\u2022\u2022\u2022 \u2022\u2022\u2022\u2022 4242\",\"credit_card_company\":\"Visa\"},\"customer\":{\"id\":2313619734625,\"email\":\"akasturi@test.com\",\"accepts_marketing\":false,\"created_at\":\"2019-09-19T13:13:02-04:00\",\"updated_at\":\"2019-10-07T10:55:20-04:00\",\"first_name\":\"Aditya\",\"last_name\":\"Kasturi\",\"orders_count\":6,\"state\":\"disabled\",\"total_spent\":\"300.00\",\"last_order_id\":1685833547873,\"note\":null,\"verified_email\":true,\"multipass_identifier\":null,\"tax_exempt\":false,\"phone\":null,\"tags\":\"\",\"last_order_name\":\"#1049\",\"currency\":\"USD\",\"accepts_marketing_updated_at\":\"2019-10-01T15:17:34-04:00\",\"marketing_opt_in_level\":null,\"admin_graphql_api_id\":\"gid:\/\/shopify\/Customer\/2313619734625\",\"default_address\":{\"id\":2608279027809,\"customer_id\":2313619734625,\"first_name\":\"Aditya\",\"last_name\":\"Kasturi\",\"company\":\"New Store \",\"address1\":\"Floor - 9\",\"address2\":\"60 South St,\",\"city\":\"Boston\",\"province\":\"Massachusetts\",\"country\":\"United States\",\"zip\":\"02111\",\"phone\":\"6148068041\",\"name\":\"Aditya Kasturi\",\"province_code\":\"MA\",\"country_code\":\"US\",\"country_name\":\"United States\",\"default\":true}}}' # pylint: disable=line-too-long
#     return json.loads(mockorder)
