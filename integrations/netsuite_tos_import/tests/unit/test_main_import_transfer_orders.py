import unittest
from unittest.mock import patch, create_autospec, call, ANY, Mock
import os
import sys
import json
import requests
import asyncio
from datetime import date, datetime
from zeep.helpers import serialize_object

sys.modules['netsuite.netsuite_environment_loader'] = Mock()


class TestTOsImport(unittest.TestCase):
    @staticmethod
    def _assert_json(test_case, json1, json2):
        if isinstance(json1, dict):
            if sys.version_info >= (3, 0):
                for key, value in json1.items():
                    TestTOsImport._assert_json(test_case, value, json2[key])
            else:
                for key, value in json1.iteritems():
                    TestTOsImport._assert_json(test_case, value, json2[key])
        elif isinstance(json1, list):
            for i, value in enumerate(json1):
                TestTOsImport._assert_json(test_case, value, json2[i])
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

        newstore_config_mock = patch('netsuite_tos_import.utils.Utils.get_newstore_config')
        self.patched_newstore_config_mock = newstore_config_mock.start()
        self.patched_newstore_config_mock.return_value = {
            "NS_URL_API": "url",
            "NS_USERNAME": "username",
            "NS_PASSWORD": "password",
            "tenant": "frankandoak"
        }

        netsuite_config_mock = patch('netsuite_tos_import.utils.Utils.get_netsuite_config')
        self.patched_netsuite_config_mock = netsuite_config_mock.start()
        self.patched_netsuite_config_mock.return_value = {
            "transfer_orders_saved_search_id": "transfer_orders_saved_search_id",
            "transfer_orders_processed_flag_script_id": "transfer_orders_processed_flag_script_id"
        }

        netsuite_location_mock = patch('netsuite_tos_import.utils.Utils.get_netsuite_location_map')
        self.patched_netsuite_location_mock = netsuite_location_mock.start()
        self.patched_netsuite_location_mock.return_value = {
            "location_1_id_nom": {"id": 1, "ff_node_id": "node_id_1"}
        }

        from netsuite_tos_import.aws.main import import_transfer_orders
        self.import_transfer_orders = import_transfer_orders

    @patch('netsuite_tos_import.aws.main.mark_to_imported_by_newstore', autospec=True)
    @patch('netsuite_tos_import.aws.main.create_transfer', autospec=True)
    @patch('netsuite_tos_import.aws.main.get_transfer_order', autospec=True)
    @patch('netsuite_tos_import.aws.main.run_transfer_order_ss', autospec=True)
    def test_import_transfer_orders(self, mock_run_transfer_order_ss, mock_get_transfer_order,
                                    mock_create_transfer, mock_mark_to_imported_by_newstore):
        saved_search_results = TestTOsImport._load_json_file('saved_search_results.json')
        transfer_order = TestTOsImport._load_json_file('transfer_order.json')
        transfer_order['tranDate'] = datetime(2021, 4, 22, 9, 45, 00)
        transfer_order_transformed = TestTOsImport._load_json_file('transfer_order_transformed.json')

        func = asyncio.Future()
        func.set_result(saved_search_results)
        mock_run_transfer_order_ss.return_value = func

        func = asyncio.Future()
        func.set_result((True, transfer_order))
        mock_get_transfer_order.return_value = func

        loop_task = self.import_transfer_orders()
        TestTOsImport._loop_wrap(loop_task)

        mock_mark_to_imported_by_newstore.assert_called_with('42017096')
        transfer_order_result = mock_create_transfer.call_args[0][0]

        TestTOsImport._assert_json(self, transfer_order_result, transfer_order_transformed)
        TestTOsImport._assert_json(self, transfer_order_transformed, transfer_order_result)
