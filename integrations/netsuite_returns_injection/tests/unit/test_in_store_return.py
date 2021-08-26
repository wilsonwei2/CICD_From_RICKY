import unittest
from unittest.mock import patch
import os
import sys
import json
import asyncio
from zeep.helpers import serialize_object
from tests.unit.data import constants
from tests.unit.data.dev_os_env import netsuite as MOCK_NETSUITE_CONFIG

PROCESS_ORDER_RETURN = None


def mock_get_product(name):
    return {
        'internalId': name
    }


class TestInStoreReturnProcessing(unittest.TestCase):
    @staticmethod
    def _assert_json(test_case, json1, json2):
        if isinstance(json1, dict):
            if sys.version_info >= (3, 0):
                for key, value in json1.items():
                    TestInStoreReturnProcessing._assert_json(test_case, value, json2[key])
            else:
                for key, value in json1.iteritems():
                    TestInStoreReturnProcessing._assert_json(test_case, value, json2[key])
        elif isinstance(json1, list):
            for i, value in enumerate(json1):
                TestInStoreReturnProcessing._assert_json(test_case, value, json2[i])
        else:
            test_case.assertEqual(json1, json2)

    @staticmethod
    def _load_json_file(filename):
        filepath = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'fixtures', filename)
        with open(filepath) as json_content:
            return json.load(json_content)

    @staticmethod
    def _loop_wrap(func):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(func)
        loop.stop()
        loop.close()
        return result

    def setUp(self):
        self.variables = {
            'TENANT': 'frankandoak',
            'STAGE': 'x',
            'netsuite_account_id': '100000',
            'netsuite_application_id': 'NOT_SET',
            'netsuite_email': 'NOT_SET',
            'netsuite_password': 'NOT_SET',
            'netsuite_role_id': 'NOT_SET',
            'netsuite_wsdl_url': 'https://webservices.netsuite.com/wsdl/v2018_1_0/netsuite.wsdl'
        }
        self.os_env = patch.dict('os.environ', self.variables)
        self.os_env.start()

        patcher_netsuite_login = patch('netsuite.service.client.service.login')
        self.patched_netsuite_login = patcher_netsuite_login.start()
        self.patched_netsuite_login.return_value = {'status': 'OK'}

        newstore_config_mock = patch('netsuite_returns_injection.helpers.utils.Utils._get_newstore_config')
        self.patched_newstore_config_mock = newstore_config_mock.start()
        self.patched_newstore_config_mock.return_value = {
            "host": "url",
            "username": "username",
            "password": "password"
        }

        netsuite_config_mock = patch('netsuite_returns_injection.helpers.utils.Utils.get_netsuite_config')
        self.patched_netsuite_config_mock = netsuite_config_mock.start()
        self.patched_netsuite_config_mock.return_value = MOCK_NETSUITE_CONFIG

        netsuite_taxmgr_config_mock = patch('pom_common.netsuite.tax_manager.TaxManager._get_netsuite_config')
        self.patched_netsuite_taxmgr_config_mock = netsuite_taxmgr_config_mock.start()
        self.patched_netsuite_taxmgr_config_mock.return_value = MOCK_NETSUITE_CONFIG

        constants.setup_patches(self)

        from netsuite_returns_injection.transformers import process_order_return
        global PROCESS_ORDER_RETURN
        PROCESS_ORDER_RETURN = process_order_return

    @patch('netsuite_returns_injection.transformers.return_transformer.get_product_by_name', side_effect=mock_get_product)
    def test_parse_order(self, mock_get_product_by_name):
        event = TestInStoreReturnProcessing._load_json_file('payload.json')
        order = TestInStoreReturnProcessing._load_json_file('order.json')
        order_parsed = TestInStoreReturnProcessing._load_json_file('order_parsed.json')
        payments = TestInStoreReturnProcessing._load_json_file('payments.json')

        customer_order = {
            'products': [
                {
                    'id': '4913',
                    'status': 'returned',
                    'sales_order_item_uuid': '5e7f4eab-d5bf-4511-8cff-4085ad8ea650',
                    'price_tax': 0.00,
                    'price_catalog': 68.00,
                    'discounts': []
                }
            ]
        }
        process = PROCESS_ORDER_RETURN.transform_order(cash_sale=order,  # NetSuite associated cash sale
                                                       ns_return=event['order'],  # Event from event stream/SQS
                                                       payments_info=payments,
                                                       customer_order=customer_order,  # NwS Customer Order
                                                       store_tz="America/Los_Angeles")
        response_order = TestInStoreReturnProcessing._loop_wrap(process)
        response_order = serialize_object(response_order)
        TestInStoreReturnProcessing._assert_json(self, response_order, order_parsed)

    @patch('netsuite_returns_injection.transformers.return_transformer.get_product_by_name', side_effect=mock_get_product)
    def test_parse_order_UN000073431(self, mock_get_product_by_name):
        event = TestInStoreReturnProcessing._load_json_file('payload_UN000073431.json')
        order = TestInStoreReturnProcessing._load_json_file('cash_sale_UN000073431.json')
        order_parsed = TestInStoreReturnProcessing._load_json_file('order_parsed_UN000073431.json')
        payments = TestInStoreReturnProcessing._load_json_file('payments_UN000073431.json')

        customer_order = {
            'products': [
                {
                    'id': '31258',
                    'status': 'returned',
                    'sales_order_item_uuid': '9db7a56d-eb89-4359-b39e-c9460cffe454',
                    'price_tax': 0.00,
                    'price_catalog': 88.00,
                    'discounts': []
                },
                {
                    'id': '35173',
                    'status': 'returned',
                    'sales_order_item_uuid': 'cde59730-f985-45ae-9dcc-352c54f0d470',
                    'price_tax': 0.00,
                    'price_catalog': 78.00,
                    'discounts': []
                }
            ]
        }
        process = PROCESS_ORDER_RETURN.transform_order(cash_sale=order,  # NetSuite associated cash sale
                                                       ns_return=event['order'],  # Event from event stream/SQS
                                                       payments_info=payments,
                                                       customer_order=customer_order,  # NwS Customer Order
                                                       store_tz="America/Los_Angeles")
        response_order = TestInStoreReturnProcessing._loop_wrap(process)
        response_order = serialize_object(response_order)
        TestInStoreReturnProcessing._assert_json(self, response_order, order_parsed)

    @patch('netsuite_returns_injection.transformers.return_transformer.get_product_by_name', side_effect=mock_get_product)
    def test_parse_order_UN000063769(self, mock_get_product_by_name):
        event = TestInStoreReturnProcessing._load_json_file('payload_UN000063769.json')
        order = TestInStoreReturnProcessing._load_json_file('cash_sale_UN000063769.json')
        order_parsed = TestInStoreReturnProcessing._load_json_file('order_parsed_UN000063769.json')
        payments = TestInStoreReturnProcessing._load_json_file('payments_UN000063769.json')

        customer_order = {
            'products': [
                {
                    'id': '4913',
                    'status': 'returned',
                    'sales_order_item_uuid': '4a6b0a97-5af7-4cc8-a9ff-4874b7f78947',
                    'price_tax': 9.02,
                    'price_catalog': 88.00,
                    'discounts': []
                },
                {
                    'id': '35173BluSlmXL',
                    'status': 'returned',
                    'sales_order_item_uuid': 'cde59730-f985-45ae-9dcc-352c54f0d470',
                    'price_tax': 0.00,
                    'price_catalog': 78.00,
                    'discounts': []
                }
            ]
        }
        process = PROCESS_ORDER_RETURN.transform_order(cash_sale=order,  # NetSuite associated cash sale
                                                       ns_return=event['order'],  # Event from event stream/SQS
                                                       payments_info=payments,
                                                       customer_order=customer_order,  # NwS Customer Order
                                                       store_tz="America/Los_Angeles")
        response_order = TestInStoreReturnProcessing._loop_wrap(process)
        response_order = serialize_object(response_order)
        TestInStoreReturnProcessing._assert_json(self, response_order, order_parsed)

    @patch('netsuite_returns_injection.transformers.return_transformer.get_product_by_name', side_effect=mock_get_product)
    def test_parse_order_with_exchange(self, mock_get_product_by_name):
        event = TestInStoreReturnProcessing._load_json_file('payload.json')
        order = TestInStoreReturnProcessing._load_json_file('order.json')
        order_parsed = TestInStoreReturnProcessing._load_json_file('order_exchange_parsed.json')
        payments = TestInStoreReturnProcessing._load_json_file('payments_exchanged_order.json')

        event['order']['total_refund_amount'] = 189.44

        customer_order = {
            'products': [
                {
                    'id': '64',
                    'status': 'returned',
                    'sales_order_item_uuid': '5e7f4eab-d5bf-4511-8cff-4085ad8ea650',
                    'price_tax': 0.00,
                    'price_catalog': 68.00,
                    'discounts': []
                }
            ]
        }
        process = PROCESS_ORDER_RETURN.transform_order(cash_sale=order,  # NetSuite associated cash sale
                                                       ns_return=event['order'],  # Event from event stream/SQS
                                                       payments_info=payments,
                                                       customer_order=customer_order,  # NwS Customer Order
                                                       store_tz="America/Los_Angeles")
        response_order = TestInStoreReturnProcessing._loop_wrap(process)
        response_order = serialize_object(response_order)
        TestInStoreReturnProcessing._assert_json(self, response_order, order_parsed)

    @patch('netsuite_returns_injection.transformers.return_transformer.get_product_by_name', side_effect=mock_get_product)
    def test_parse_order_without_refund_payments(self, mock_get_product_by_name):
        event = TestInStoreReturnProcessing._load_json_file('payload.json')
        order = TestInStoreReturnProcessing._load_json_file('cash_sale_with_discount_and_gc.json')
        payments = TestInStoreReturnProcessing._load_json_file('payments_without_refund.json')
        return_json = TestInStoreReturnProcessing._load_json_file('return.json')

        returned_product_internal_ids = {}

        with self.assertRaises(Exception):
            TestInStoreReturnProcessing._loop_wrap(PROCESS_ORDER_RETURN.transform_order(returned_product_internal_ids, order, event['order'], payments, return_json))

    @patch('netsuite_returns_injection.transformers.return_transformer.get_product_by_name', side_effect=mock_get_product)
    def test_parse_order_with_discount(self, mock_get_product_by_name):
        event = TestInStoreReturnProcessing._load_json_file('payload.json')
        order = TestInStoreReturnProcessing._load_json_file('cash_sale_with_discount_and_gc.json')
        order_parsed = TestInStoreReturnProcessing._load_json_file('cash_sale_with_discount_and_gc_parsed.json')
        payments = TestInStoreReturnProcessing._load_json_file('payments_with_gc.json')

        event['order']['total_refund_amount'] = 147.15

        customer_order = {
            'products': [
                {
                    'id': '8232',
                    'status': 'returned',
                    'sales_order_item_uuid': '5e7f4eab-d5bf-4511-8cff-4085ad8ea650',
                    'price_tax': 0.00,
                    'price_catalog': 68.00,
                    'discounts': [
                        {
                            "coupon_code": "COUPON1",
                            "level": "item",
                            "price_adjustment": 10,
                            "reason": "",
                            "type": "fixed",
                            "value": 10
                        }
                    ],
                    'external_identifiers': [
                        {
                            'type': 'serial_number',
                            'value': '111111111111'
                        }
                    ]
                }
            ]
        }

        response_order = TestInStoreReturnProcessing._loop_wrap(PROCESS_ORDER_RETURN.transform_order(cash_sale=order,  # NetSuite associated cash sale
                                                                            ns_return=event['order'],  # Event from event stream/SQS
                                                                            payments_info=payments,
                                                                            customer_order=customer_order,  # NwS Customer Order
                                                                            store_tz="America/Los_Angeles"))
        response_order = serialize_object(response_order)
        TestInStoreReturnProcessing._assert_json(self, response_order, order_parsed)

    @patch('netsuite_returns_injection.transformers.return_transformer.get_product_by_name', side_effect=mock_get_product)
    def test_parse_partial_return_with_discount(self, mock_get_product_by_name):
        event = TestInStoreReturnProcessing._load_json_file('payload_partial_return_1.json')
        order = TestInStoreReturnProcessing._load_json_file('cash_sale_partial_return_with_discount.json')
        order['subsidiary']['internalId'] = '1'
        order_parsed = TestInStoreReturnProcessing._load_json_file('cash_sale_partial_return_with_discount_parsed.json')
        payments = TestInStoreReturnProcessing._load_json_file('payments_with_discount.json')
        customer_order = TestInStoreReturnProcessing._load_json_file('customer_order_with_discount.json')['customer_order']

        response_order = TestInStoreReturnProcessing._loop_wrap(PROCESS_ORDER_RETURN.transform_order(cash_sale=order,  # NetSuite associated cash sale
                                                                            ns_return=event['order'],  # Event from event stream/SQS
                                                                            payments_info=payments,
                                                                            customer_order=customer_order,  # NwS Customer Order
                                                                            store_tz="America/Los_Angeles"))
        response_order = serialize_object(response_order)

        TestInStoreReturnProcessing._assert_json(self, response_order, order_parsed)
