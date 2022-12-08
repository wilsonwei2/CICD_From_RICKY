import requests
import json
import logging

from yotpo_shopper_loyalty.handlers.utils import Utils

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

class YotpoHandler:

    def __init__(self) -> None:
        utils = Utils.get_instance()
        self.param_store = utils.get_parameter_store()
        self.yotpo_order_url = self.param_store.get_param('yotpo_order_url')
        self.yotpo_refund_url = self.param_store.get_param('yotpo_refund_url')
        self.yotpo_api_key = self.param_store.get_param('yotpo_api_key')
        self.yotpo_api_guid = self.param_store.get_param('yotpo_api_guid')
        self.ns_handler = utils.get_ns_handler()

    def create_order(self, order_data: dict):
        """
        Create a new order in Yotpo
        """
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self.yotpo_api_key,
            'x-guid': self.yotpo_api_guid
        }
        yotpo_order_data = self._map_order_data(order_data)
        LOGGER.info(f'Yotpo order creation payload data: {yotpo_order_data}')
        response = requests.post(self.yotpo_order_url, headers=headers, data=json.dumps(yotpo_order_data))
        LOGGER.info(f'Yotpo order creation response: {response.text}')
        if response.status_code not in [200, 201]:
            LOGGER.error(f'Failed to create order in Yotpo: {response.text}')
            return False
        return True

    def create_refund(self, refund_data: dict):
        """
        Create a new refund in Yotpo
        """
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self.yotpo_api_key,
            'x-guid': self.yotpo_api_guid
        }
        LOGGER.info(f'Yotpo refund creation payload data: {refund_data}')
        response = requests.post(self.yotpo_refund_url, headers=headers, data=json.dumps(refund_data))
        LOGGER.info(f'Yotpo refund creation response: {response.text}')
        if response.status_code not in [200, 201]:
            LOGGER.error(f'Failed to create refund in Yotpo: {response.text}')
            return False
        return True

    def _map_order_data(self, order_data: dict) -> dict:
        yotpo_order = {}
        yotpo_order['customer_email'] = order_data.get('customer_email')
        yotpo_order['total_amount_cents'] = int(float(order_data.get('subtotal') * 100))
        yotpo_order['currency_code'] = order_data.get('currency')
        yotpo_order['order_id'] = order_data.get('external_id')
        yotpo_order['created_at'] = order_data.get('created_at')
        yotpo_order['coupon_code'] = self._get_ns_coupons(order_data)
        yotpo_order['ip_address'] = '0.0.0.0'
        yotpo_order['user_agent'] = 'NewStore Yotpo integration'
        yotpo_order['discount_amount_cents'] = int(float(order_data.get('discount_total') * 100))
        yotpo_order['items'] = self._get_order_items(order_data)
        yotpo_order['customer'] = self._get_customer_data(order_data)
        yotpo_order['ignore_ip_ua'] = True
        return yotpo_order

    def _get_ns_coupons(self, order_opened_payload) -> list:
        if not order_opened_payload.get('discounts'):
            return None
        ns_coupons = []
        for discount in order_opened_payload.get('discounts'):
            coupon_code = discount.get('coupon_code')
            if coupon_code.startswith('FAOC') or coupon_code.startswith('FAOU'):
                ns_coupons.append(coupon_code)
        return ",".join(ns_coupons)

    def _get_order_items(self, order_data: dict) -> list:
        order_items = []
        for item in order_data.get('items'):
            product_details = self.ns_handler.get_product(item.get('external_identifiers').get('sku'))
            order_items.append({
                'name': product_details.get('title'),
                'quantity': item.get('quantity'),
                'price_cents': item.get('list_price') * 100 + item.get('tax') * 100,
                'id': product_details.get('product_id')
            })
        return order_items

    def _get_customer_data(self, order_data: dict) -> dict:
        return {
            'email': order_data.get('customer_email'),
            'first_name': order_data.get('customer_first_name'),
            'last_name': order_data.get('customer_last_name'),
            'phone': order_data.get('customer_phone')
        }
