import unittest
from unittest.mock import patch
import os
import sys
import json
import asyncio
from zeep.helpers import serialize_object
from tests.unit.data import constants
from tests.unit.data.dev_os_env import netsuite as MOCK_NETSUITE_CONFIG

PROCESS_APPEASEMENT = None


class TestAppeasementRefund(unittest.TestCase):
    @staticmethod
    def _assert_json(test_case, json1, json2):
        if isinstance(json1, dict):
            if sys.version_info >= (3, 0):
                for key, value in json1.items():
                    TestAppeasementRefund._assert_json(test_case, value, json2[key])
            else:
                for key, value in json1.iteritems():
                    TestAppeasementRefund._assert_json(test_case, value, json2[key])
        elif isinstance(json1, list):
            for i, value in enumerate(json1):
                TestAppeasementRefund._assert_json(test_case, value, json2[i])
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
            'TENANT_NAME': 'frankandoak',
            'NEWSTORE_STAGE': 'x',
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

        newstore_config_mock = patch('netsuite_appeasement_refund_injection.helpers.utils.Utils._get_newstore_config')
        self.patched_newstore_config_mock = newstore_config_mock.start()
        self.patched_newstore_config_mock.return_value = {
            "host": "url",
            "username": "username",
            "password": "password"
        }

        netsuite_config_mock = patch('netsuite_appeasement_refund_injection.helpers.utils.Utils.get_netsuite_config')
        self.patched_netsuite_config_mock = netsuite_config_mock.start()
        self.patched_netsuite_config_mock.return_value = MOCK_NETSUITE_CONFIG

        constants.setup_patches(self)

        from netsuite_appeasement_refund_injection.transformers import process_appeasement
        global PROCESS_APPEASEMENT
        PROCESS_APPEASEMENT = process_appeasement

    #@patch('transformers.utils.get_gc_last_digits', autospec=True)
    def test_transform_in_store_order_refund(self):#, mock_get_gc_last_digits):
        event_refund = TestAppeasementRefund._load_json_file('event_refund.json')['event']['payload']
        customer_order = TestAppeasementRefund._load_json_file('customer_order.json')['customer_order']
        payments_info = TestAppeasementRefund._load_json_file('payments_info.json')
        expected_result = TestAppeasementRefund._load_json_file('in_store_cash_refund_transformed.json')

        #mock_get_gc_last_digits.return_value = '1234'
        store_tz = 'America/New_York'
        cash_sale = {
            'internalId': '1000',
            'entity': {'internalId': '10'}
        }

        result = TestAppeasementRefund._loop_wrap(PROCESS_APPEASEMENT.transform_in_store_order_refund(cash_sale, event_refund, customer_order, payments_info, store_tz))
        result = serialize_object(result)

        TestAppeasementRefund._assert_json(self, result, expected_result)

    def test_map_cash_refund(self):
        event_refund = TestAppeasementRefund._load_json_file('event_refund.json')['event']['payload']
        expected_result = TestAppeasementRefund._load_json_file('cash_refund_mapped.json')
        cash_refund_custom_fields = TestAppeasementRefund._load_json_file('custom_fields_mapped.json')

        location_id = 100
        subsidiary_id = 10
        store_tz = 'America/New_York'

        result = PROCESS_APPEASEMENT.map_cash_refund(subsidiary_id, event_refund, location_id, cash_refund_custom_fields, store_tz)
        result = serialize_object(result)

        TestAppeasementRefund._assert_json(self, result, expected_result)

    def test_map_cash_refund_item(self):
        event_refund = TestAppeasementRefund._load_json_file('event_refund.json')['event']['payload']
        expected_result = TestAppeasementRefund._load_json_file('cash_refund_items_mapped.json')

        result = PROCESS_APPEASEMENT.map_cash_refund_item(event_refund, 1, 5)
        result = serialize_object(result)

        TestAppeasementRefund._assert_json(self, result, expected_result)

    #@patch('transformers.utils.get_gc_last_digits', autospec=True)
    def test_map_payments(self):#, mock_get_gc_last_digits):
        event_refund = TestAppeasementRefund._load_json_file('event_refund.json')['event']['payload']
        payments_info = TestAppeasementRefund._load_json_file('payments_info.json')
        expected_result = TestAppeasementRefund._load_json_file('payments_mapped.json')

        #mock_get_gc_last_digits.return_value = '1234'
        result, _ = TestAppeasementRefund._loop_wrap(PROCESS_APPEASEMENT.map_payment_items(payment_instrument_list=payments_info['instruments'],
                                                    ns_return=event_refund,
                                                    subsidiary_id=1,
                                                    store_tz="America/New_York",
                                                    location_id=1))
        result = serialize_object(result)

        TestAppeasementRefund._assert_json(self, result, expected_result)

    def test_map_custom_fields(self):
        customer_order = TestAppeasementRefund._load_json_file('customer_order.json')['customer_order']
        expected_result = TestAppeasementRefund._load_json_file('custom_fields_mapped.json')

        result = PROCESS_APPEASEMENT.map_cash_refund_custom_fields(customer_order)
        result = serialize_object(result)

        TestAppeasementRefund._assert_json(self, result, expected_result)
