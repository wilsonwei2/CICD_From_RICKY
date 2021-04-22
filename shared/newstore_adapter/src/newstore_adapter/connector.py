import logging
import json
import os
from requests.utils import quote
from .exceptions import NewStoreAdapterException
from .adapter import NewStoreAdapter

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class NewStoreConnector(object):
    def __init__(self, tenant, context, username=None, password=None, host=None, raise_errors=False):
        self.newstore_adapter = NewStoreAdapter(tenant, context, username, password, host)
        self.host = host if host else os.environ.get('newstore_url_api')
        self.raise_errors = raise_errors

    def get_external_order(self, external_order_id, email=None, country_cod=None, id_type=None):
        if id_type is not None:
            external_order_id = "%s=%s" % (id_type, external_order_id)

        url = 'https://%s/v0/d/external_orders/%s' % (self.host, external_order_id)
        search_params = {}
        if email:
            search_params['email'] = email
        if country_cod:
            search_params['country_code'] = country_cod
        try:
            response = self.newstore_adapter.get_request(url, search_params)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return None
        return response.json()

    def get_customer_order(self, order_id):
        url = 'https://%s/v0/c/customer_orders/%s' % (self.host, order_id)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    def get_customer_orders(self, customer_id):
        url = 'https://%s/v0/d/consumer_profiles/%s/orders?count=2000' % (self.host, customer_id)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json().get('items', [])

    def get_order(self, order_id):
        url = 'https://%s/v0/c/orders/%s' % (self.host, order_id)
        try:
            response = self.newstore_adapter.patch_request(url)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    ###
    # Inject order in NewStore
    # param order_data: json for order to be injected
    # param raise_error: flag to whether raise error in case something happens
    # or just return None and let lambda handle it
    ###

    def fulfill_order(self, order_data, raise_error=False):
        url = 'https://%s/v0/d/fulfill_order' % (self.host)
        try:
            response = self.newstore_adapter.post_request(url, order_data)
        except Exception as ns_err:
            error = (ns_err.args[0])
            args = json.loads(error)
            if args.get('error_code') == 'same_order_injection_with_different_data':
                logger.info(args.get('message'))
                logger.info('Sending 200 Response to the order that is already processed')
                return {
                    'error_code': 'same_order_injection_with_different_data',
                    'body': 'order processed already in Newstore'
                }

            elif raise_error or self.raise_errors:
                raise
            return None

        return response.json()

    def get_return(self, order_id, return_id):
        url = 'https://%s/v0/d/orders/%s/returns/%s' % (self.host, order_id, return_id)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    def get_returns(self, order_id):
        url = 'https://%s/v0/d/orders/%s/returns' % (self.host, order_id)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    def get_store(self, store_id):
        url = 'https://%s/_/v0/dontuse/stores/%s' % (self.host, store_id)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return None
        return response.json()


    def get_stores(self):
        url = 'https://%s/_/v0/dontuse/stores' % (self.host)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return None
        return response.json()

    def get_payments(self, account_id):
        url = 'https://%s/v0/c/payments/accounts/%s' % (self.host, str(account_id))
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return None
        return response.json()

    def get_hq_payments(self, account_id):
        url = 'https://%s/_/v0/hq/payments/%s' % (self.host, str(account_id))
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException:
            return {}
        return response.json()

    def get_product(self, product_id, shop, locale, id_type=None):

        if id_type is not None:
            product_id = "%s=%s" % (id_type, product_id)

        url = 'https://%s/v0/c/products/%s' % (self.host, str(product_id))
        params = {
            'shop': shop,
            'locale': locale
        }
        try:
            response = self.newstore_adapter.get_request(url, params, False)
        except NewStoreAdapterException:
            return None
        return response.json()

    def find_product(self, key, value, shop, locale, params):
        """
        Get the product by identifier type from the consumer API
        https://aninebing.x.newstore.net/api/v1/shops/storefront-catalog-en/products/sku=AB30-064-15-?locale=en-US
        :param ctx: The context containing the url and auth
        :param key: key to look for
        :param value: value  of the key
        :param params: the params to pass in the call
        :return: the json [arsed response
        """
        if value:
            value = quote(value, safe='')
            url = 'https://%s/api/v1/shops/%s/products/%s=%s' % (self.host, shop, key, value)
            if locale:
                if not params:
                    params = {}
                params['locale'] = locale

            try:
                response = self.newstore_adapter.get_request(url, params, False)
            except NewStoreAdapterException:
                return None
            return response.json()
        return None

    def get_consumer(self, email, offset=0):
        url = 'https://%s/v0/d/consumer_profiles' % (self.host)
        params = {
            'q': email,
            'offset': offset
        }
        try:
            response = self.newstore_adapter.get_request(url, params)
        except NewStoreAdapterException:
            return None
        # Consumer profiles can return partial matches, so we search for the right one
        consumer_profiles = response.json()
        for consumer in consumer_profiles['items']:
            if consumer['email'].lower() == email.lower():
                logger.info('Consumer found.')
                logger.info(json.dumps(consumer, indent=4))
                return consumer
        # If the consumer profile is not found we check count and total of profiles
        # And call again if there are still profiles to be get on NewStore
        if int(consumer_profiles.get('pagination_info', {}).get('count')) + offset \
                < int(consumer_profiles.get('pagination_info', {}).get('total')):
            return self.get_consumer(email, offset + int(consumer_profiles.get('pagination_info', {}).get('count')))
        # If there is no consumer, return None
        logger.info('No consumer found')
        return None

    def get_consumer_with_id(self, consumer_id, offset=0):
        url = 'https://%s/v0/d/consumer_profiles/%s' % (self.host, consumer_id)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return None
        return response.json()

    def get_employees(self):
        url = 'https://%s/_/v0/dontuse/employees' % (self.host)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException:
            return None
        return response.json()

    def get_employee(self, employee_id):
        url = 'https://%s/_/v0/dontuse/employees/%s' % (self.host, employee_id)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException:
            return None
        return response.json()


    def send_acknowledgement(self, ff_id):
        url = 'https://%s/v0/d/fulfillment_requests/%s/acknowledgement' % (self.host, ff_id)
        try:
            self.newstore_adapter.post_request(url, {})
        except NewStoreAdapterException:
            return False
        return True

    ###
    # Utilized when rejecting the whole fulfillment request
    # params reason: Rejection reasons are cannot_fulfill or no_inventory
    #                When using cannot_fulfill items_json is empty
    #                When using no_inventory a list of the missing products has to be passed on items_json
    # params ff_id: fulfillment request id
    # params auth: Authentication
    # params items_json: Is a simple array with product ids/sku
    ###

    def send_rejection(self, reason, ff_id, items_json=[]):
        response_json = {
            'rejection_reason': reason,
            'missing_product_ids': items_json
        }

        url = 'https://%s/v0/d/fulfillment_requests/%s/rejection' % (self.host, ff_id)
        try:
            self.newstore_adapter.post_request(url, response_json)
        except NewStoreAdapterException:
            return False
        return True

    ###
    # Utilized when rejecting only part of the fulfillment request
    # params reason: Rejection reasons are cannot_fulfill or no_inventory
    # params ff_id: fulfillment request id
    # params items_json: Is a simple array with product ids/sku
    ###

    def send_item_rejection(self, reason, ff_id, items_json=[]):
        response_json = {
            'missing_items': [
                {
                    'reason': reason,
                    'product_ids': items_json
                }
            ]
        }

        url = 'https://%s/v0/d/fulfillment_requests/%s/reject_items' % (self.host, ff_id)
        try:
            self.newstore_adapter.post_request(url, response_json)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return False
        return True

    ###
    # Utilized when cancelling part of the fulfillment request
    # params ff_id: fulfillment request id
    # params items_json: Is a simple array with product ids
    ###
    def send_item_cancelation(self, ff_id, items_json=[]):
        request_json = {
            'product_ids': items_json
        }

        url = 'https://%s/v0/d/fulfillment_requests/%s/canceled_items' % (self.host, ff_id)
        try:
            self.newstore_adapter.post_request(url, request_json)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return False
        return True


    ###
    # params response_json: it's the shipping details and must be in the following format
    # {
    #   'line_items': [
    #       {
    #           'product_ids': ['SKU001','SKU001','SKU002'],
    #           'shipment': {
    #               'tracking_code': 'tracking_reference',
    #               'carrier': 'carrier'
    #           }
    #       }
    #   ]
    # }
    # Send POST request to /fulfillment_requests/{ff_id}/shipment
    ###

    def send_shipment(self, ff_id, response_json):
        url = 'https://%s/v0/d/fulfillment_requests/%s/shipment' % (self.host, ff_id)
        try:
            self.newstore_adapter.post_request(url, response_json)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return False
        return True

    # Send GET request to /fulfillment_requests/{ff_id}/shipment
    def get_shipments(self, ff_id):
        url = 'https://%s/v0/d/fulfillment_requests/%s/shipment' % (self.host, ff_id)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException:
            return None
        return response.json()

    ###
    # Create a Newstore return based on array of items and returned_from identifier.
    #
    # param order_id: Newstore order_id related to return
    # param return_json:  Returned `items` are an array of objects with at least
    #   one property called "product_id" which could be the sku or other id.
    # {
    #   "items": [
    #       {
    #           "product_id": "SKU001",
    #           "reason": "Item was damaged."
    #       }
    #   ],
    #   "returned_from": "27a39710-4b2d-43fd-b636-5f7aed3073a2"
    # }
    #
    # return: JSON response from Newstore API. Example response:
    #   https://apidoc.newstore.io/v0/s/documentation/newstore-cloud/newstore.html#create-return-respexple
    #
    # Send POST request to /orders/{order_id}/returns
    ###

    def create_return(self, order_id, return_json):
        url = 'https://%s/v0/d/orders/%s/returns' % (self.host, order_id)
        try:
            response = self.newstore_adapter.post_request(url, return_json)
        except NewStoreAdapterException:
            return None
        return response.json()

    def create_inventory_count_task(self, store_id, count_task_payload):
        url = 'https://%s/v0/i/inventory/stores/%s/count_tasks' % (self.host, store_id)
        try:
            response = self.newstore_adapter.post_request(url, count_task_payload)
        except NewStoreAdapterException:
            return None
        return response.json()

    def get_inventory_count_task(self, inv_count_id):
        url = 'https://%s/v0/i/inventory/count_tasks/%s' % (self.host, inv_count_id)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException:
            return None
        return response.json()

    def get_refund(self, order_id, refund_id):
        url = 'https://%s/v0/d/orders/%s/refunds/%s' % (self.host, order_id, refund_id)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    def get_refunds(self, order_id):
        url = 'https://%s/v0/d/orders/%s/refunds' % (self.host, order_id)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json().get('refunds', [])

    def create_refund(self, order_id, refund_json):
        url = 'https://%s/v0/d/orders/%s/refunds' % (self.host, order_id)
        try:
            response = self.newstore_adapter.post_request(url, refund_json)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    def get_integrations(self):
        url = 'https://%s/api/v1/org/integrations/eventstream' % (self.host)
        logger.info(
            'Getting integrations values from newstore %s', url)
        response = self.newstore_adapter.get_request(url)
        return response.json()

    def get_integration(self, name):
        url = 'https://%s/api/v1/org/integrations/eventstream/%s' % (self.host, name)
        logger.info(
            'Getting resource integration from newstore %s', url)
        response = self.newstore_adapter.get_request(url)
        return response.json()

    def create_integration(self, name, callback, filters=None):
        url = 'https://%s/api/v1/org/integrations/eventstream' % (self.host)
        logger.info(
            'Creating integration %s with newstore %s', name, url)
        payload = {
            'id': name,
            'callback_parameters': {'callback_url': callback},
            'integration_type': 'permanent'
        }

        if filters:
            payload['filter_conditions'] = filters

        logger.info('Webhook info:\n%s', json.dumps(payload))
        response = self.newstore_adapter.post_request(url, payload)
        return response.json()

    def start_integration(self, name):
        url = 'https://%s/api/v1/org/integrations/eventstream/%s/_start' % (self.host, name)
        logger.info(
            'Starting integration %s with newstore', name)
        response = self.newstore_adapter.post_request(url, {})
        return response.json()

    def create_asn(self, asn):
        url = 'https://%s/v0/i/inventory/asns' % (self.host)
        try:
            response = self.newstore_adapter.post_request(url, asn)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    def get_asn(self, asn_id):
        url = 'https://%s/v0/i/inventory/asns/%s' % (self.host, asn_id)
        logger.info('Getting ASN from newstore %s', url)
        response = self.newstore_adapter.get_request(url)
        return response.json()


    def get_asns_by_store(self, store_id, status='open'):
        url = f'https://{self.host}/v0/i/inventory/stores/{store_id}/asns'
        status = {
            'status': status
        }
        logger.info('Getting ASN list from Newstore %s', url)
        response = self.newstore_adapter.get_request(url, search_json=status)
        return response.json()

    def extend_grace_period(self, order_id):
        """ Extend orders grace period to datetime - PRIVATE API """
        url = 'https://%s/_/v0/hq/customer_orders/%s/_extend_grace_period' % (self.host, order_id)
        try:
            response = self.newstore_adapter.post_request(url, {})
        except Exception as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    def extend_grace_period_ns_order(self, order_id):
        """ Extend orders grace period to datetime - PRIVATE API """
        url = 'https://%s/_/v0/hq/customer_orders/%s/_extend_grace_period' % (self.host, order_id)
        try:
            response = self.newstore_adapter.post_request(url, {})
        except Exception as ns_err:
            if self.raise_errors:
                raise ns_err
            else:
                return ns_err
        return response.json()

    def cancel_order(self, order_id):
        """ Cancel specific order - PRIVATE API """
        url = 'https://%s/_/v0/hq/customer_orders/%s/cancellation' % (self.host, order_id)
        try:
            response = self.newstore_adapter.post_request(url, {})
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    def cancel_ns_order(self, order_id, reason, note):
        """ Cancel specific order - PRIVATE API """
        url = 'https://%s/_/v0/hq/customer_orders/%s/cancellation' % (self.host, order_id)
        try:
            info = {
                "reason": reason,
                "note": note
            }
            resp = self.newstore_adapter.post_request(url, info)
            logger.info(f'response from cancel API is {resp}')
            response = resp.json()
            logger.info(f'response after JSON conversion is {response}')
            if response.get('success') == 'true' or response.get('success') is True:
                return True
            elif response.get('error', '').get('code', '') == 'order_already_canceled':
                logger.info('Order is already cancelled, dummying up 200 response to release the order')
                return True
            else:
                return False
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return False

    def add_order_notes(self, order_id, order_notes):
        """ Extend orders grace period to datetime - PRIVATE API """
        url = 'https://%s/v0/d/orders/%s/notes' % (self.host, order_id)
        try:
            info = order_notes
            response = self.newstore_adapter.post_request(url, info)
        except Exception as ns_err:
            if self.raise_errors:
                raise
            return None
        return response.json()

    def set_order_cancellation_information(self, order_id, reason, note=None):
        """ Set information about order cancellation - PRIVATE API """
        url = 'https://%s/_/v0/hq/customer_orders/%s/cancellation' % (self.host, order_id)
        try:
            information = {
                "reason": reason,
                "note": note
            }
            response = self.newstore_adapter.put_request(url, information)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    # params request_json: it's the pickup location and cart contents and must be in the following format
    # {
    #   "location": {
    #     "geo": {
    #       "latitude": 19.762803,
    #       "longitude": -70.421836
    #     }
    #   },
    #   "bag": [
    #     {
    #       "product_id": "1000831",
    #       "quantity": 2
    #     },
    #     {
    #       "product_id": "1000692",
    #       "quantity": 1
    #     }
    #   ],
    #   "options": {
    #     "search_radius": 30,
    #     "show_stores_without_atp": true
    #   }
    # }
    # Send POST request to /in_store_pickup_options
    ###

    def get_in_store_pickup_options(self, request_json):
        """ Retrieve in-store pickup offer tokens based on geo location, items and search radius """
        url = 'https://%s/v0/d/in_store_pickup_options' % (self.host)

        try:
            response = self.newstore_adapter.post_request(url, request_json)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise
            return None
        return response.json()

    def get_fulfillment_config(self):
        url = 'https://%s/_/v0/dontuse/fulfillment_config' % (self.host)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    def create_import(self, payload):
        url = f'https://{self.host}/v0/d/import'
        try:
            response = self.newstore_adapter.post_request(url, payload)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    def start_import(self, import_id, payload):
        url = f'https://{self.host}/v0/d/import/{import_id}/start'
        try:
            response = self.newstore_adapter.post_request(url, payload)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    def get_reason_codes(self):
        url = 'https://%s/api/v1/org/config/reason_code_types/cancellations/reason_codes' % (self.host)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    def create_transfer_order(self, transfer_order):
        url = 'https://%s/v0/i/inventory/transfer_orders' % (self.host)
        try:
            response = self.newstore_adapter.post_request(url, transfer_order)
        except NewStoreAdapterException as ns_err:
            if self.raise_errors:
                raise ns_err
            return None
        return response.json()

    def get_transfer_order(self, transfer_order_id):
        url = 'https://%s/v0/i/inventory/transfer_orders/%s' % (self.host, transfer_order_id)
        logger.info('Getting Transfer Order from newstore %s', url)
        response = self.newstore_adapter.get_request(url)
        return response.json()

    def get_locations(self):
        url = 'https://%s/v0/locations' % (self.host)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return None
        return response.json()

    def enable_inventory_master(self, location_id):
        url = 'https://%s/v0/locations/%s/inventory_master/_enable' % (self.host, location_id)
        try:
            response = self.newstore_adapter.post_request(url, {})
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return None
        return response.json()

    def set_transfer_shipping_config(self, data):
        url = 'https://%s/v0/i/inventory/transfer_shipping_config' % (self.host)
        try:
            response = self.newstore_adapter.post_request(url, data)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return None
        return response.json()

    def get_stock_locations(self):
        url = 'https://%s/v0/stock_locations' % (self.host)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return None
        return response.json()

    def start_availability_export(self, last_updated_at=None):
        url = 'https://%s/v0/d/availabilities/bulk' % (self.host)
        try:
            response = self.newstore_adapter.post_request(url, (
                {'last_updated_at': int(last_updated_at)} if last_updated_at else {}
            ))
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return None
        return response.json()

    def get_availability_export(self, export_id):
        url = 'https://%s/v0/d/availabilities/bulk/%s' % (self.host, export_id)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return None
        return response.json()

    def get_availability_groups(self):
        url = 'https://%s/v0/d/availabilities/groups' % (self.host)
        try:
            response = self.newstore_adapter.get_request(url)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return None
        return response.json()

    def graphql(self, query, params={}):
        try:
            response = self.newstore_adapter.graphql_request(query, params)
        except NewStoreAdapterException:
            if self.raise_errors:
                raise
            return None
        return response

    ###
    # Calls GraphQL API
    # param query: GraphQL query
    # param raise_error: flag to whether raise error in case something happens
    # or just return None and let lambda handle it
    ###
    def graphql_api_call(self, query, raise_error=True):
        url = 'https://%s/api/v1/org/data/query' % (self.host)
        try:
            response = self.newstore_adapter.post_request(url, query)
        except NewStoreAdapterException as ns_err:
            if raise_error or self.raise_errors:
                raise
            return None
        return response.json()
