import unittest
from unittest.mock import patch, Mock
import os
import sys
import json
import asyncio
from zeep.helpers import serialize_object
from tests.unit.data.dev_os_env import NETSUITE as MOCK_NETSUITE_CONFIG, PAYMENTS as MOCK_PAYMENTS_CONFIG
from netsuite_cancellation_injection.helpers.utils import Utils

sys.modules['netsuite.netsuite_environment_loader'] = Mock()


class TestCancellation(unittest.TestCase):
    @staticmethod
    def _assert_json(test_case, json1, json2):
        if isinstance(json1, dict):
            if sys.version_info >= (3, 0):
                for key, value in json1.items():
                    TestCancellation._assert_json(test_case, value, json2[key])
            else:
                for key, value in json1.iteritems():
                    TestCancellation._assert_json(test_case, value, json2[key])
        elif isinstance(json1, list):
            for i, value in enumerate(json1):
                TestCancellation._assert_json(test_case, value, json2[i])
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

        netsuite_config_mock = patch('netsuite_cancellation_injection.helpers.utils.Utils.get_netsuite_config')
        self.patched_netsuite_config_mock = netsuite_config_mock.start()
        self.patched_netsuite_config_mock.return_value = MOCK_NETSUITE_CONFIG

        payments_config_mock = patch('netsuite_cancellation_injection.helpers.utils.Utils._get_payments_config')
        self.patched_payments_config_mock = payments_config_mock.start()
        self.patched_payments_config_mock.return_value = MOCK_PAYMENTS_CONFIG

        patcher_param_store = patch('param_store.client.ParamStore')
        self.patched_param_store = patcher_param_store.start()
        self.patched_param_store.return_value = {}

        from netsuite_cancellation_injection.aws import cancellation_to_netsuite
        self.cancellation_to_netsuite = cancellation_to_netsuite

    @patch('netsuite_cancellation_injection.aws.cancellation_to_netsuite.get_sales_order', autospec=True)
    @patch('netsuite_cancellation_injection.aws.cancellation_to_netsuite.update_sales_order', autospec=True)
    def test_map_order_cancellation(self, mock_update_so, mock_get_so):
        cancellation_event = TestCancellation._load_json_file('order_cancellation.json')
        sales_order = TestCancellation._load_json_file('sales_order.json')
        expected_result = TestCancellation._load_json_file('updated_so_order_cancellation.json')

        mock_get_so.return_value = sales_order

        TestCancellation._loop_wrap(self.cancellation_to_netsuite.process_cancellation(cancellation_event))
        updated_sales_order = serialize_object(mock_update_so.call_args[0][0])

        TestCancellation._assert_json(self, updated_sales_order, expected_result)

    @patch('netsuite_cancellation_injection.aws.cancellation_to_netsuite.get_sales_order', autospec=True)
    @patch('netsuite_cancellation_injection.aws.cancellation_to_netsuite.update_sales_order', autospec=True)
    def test_map_item_cancellation(self, mock_update_so, mock_get_so):
        cancellation_event = TestCancellation._load_json_file('item_cancellation.json')
        sales_order = TestCancellation._load_json_file('sales_order.json')
        expected_result = TestCancellation._load_json_file('updated_so_item_cancellation.json')

        mock_get_so.return_value = sales_order

        TestCancellation._loop_wrap(self.cancellation_to_netsuite.process_cancellation(cancellation_event))
        updated_sales_order = serialize_object(mock_update_so.call_args[0][0])

        TestCancellation._assert_json(self, updated_sales_order, expected_result)

    @patch('netsuite_cancellation_injection.aws.cancellation_to_netsuite.get_sales_order', autospec=True)
    @patch('netsuite_cancellation_injection.aws.cancellation_to_netsuite.update_sales_order', autospec=True)
    def test_map_item_cancellation_with_discount(self, mock_update_so, mock_get_so):
        cancellation_event = TestCancellation._load_json_file('item_cancellation.json')
        sales_order = TestCancellation._load_json_file('sales_order_with_discount.json')
        expected_result = TestCancellation._load_json_file('updated_so_item_cancellation_w_discount.json')

        mock_get_so.return_value = sales_order

        TestCancellation._loop_wrap(self.cancellation_to_netsuite.process_cancellation(cancellation_event))
        updated_sales_order = serialize_object(mock_update_so.call_args[0][0])

        TestCancellation._assert_json(self, updated_sales_order, expected_result)

    @patch('netsuite_cancellation_injection.aws.cancellation_to_netsuite.get_sales_order', autospec=True)
    @patch('netsuite_cancellation_injection.aws.cancellation_to_netsuite.update_sales_order', autospec=True)
    def test_map_item_cancellation_with_split_payment(self, mock_update_so, mock_get_so):
        cancellation_event = TestCancellation._load_json_file('item_cancellation.json')
        sales_order = TestCancellation._load_json_file('sales_order_with_split_payment.json')
        expected_result = TestCancellation._load_json_file('updated_so_item_cancellation_w_split_payment.json')

        mock_get_so.return_value = sales_order

        TestCancellation._loop_wrap(self.cancellation_to_netsuite.process_cancellation(cancellation_event))
        updated_sales_order = serialize_object(mock_update_so.call_args[0][0])

        TestCancellation._assert_json(self, updated_sales_order, expected_result)
