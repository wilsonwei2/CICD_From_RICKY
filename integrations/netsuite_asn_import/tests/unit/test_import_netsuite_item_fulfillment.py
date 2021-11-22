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


class TestFrankandoakASNImport(unittest.TestCase):
    @staticmethod
    def _assert_json(test_case, json1, json2):
        if isinstance(json1, dict):
            if sys.version_info >= (3, 0):
                for key, value in json1.items():
                    TestFrankandoakASNImport._assert_json(test_case, value, json2[key])
            else:
                for key, value in json1.iteritems():
                    TestFrankandoakASNImport._assert_json(test_case, value, json2[key])
        elif isinstance(json1, list):
            for i, value in enumerate(json1):
                TestFrankandoakASNImport._assert_json(test_case, value, json2[i])
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
            'SQS_QUEUE': 'SQS_QUEUE',
            'netsuite_account_id': '100000',
            'netsuite_application_id': 'NOT_SET',
            'netsuite_email': 'NOT_SET',
            'netsuite_password': 'NOT_SET',
            'netsuite_role_id': 'NOT_SET',
            'netsuite_wsdl_url': 'https://webservices.netsuite.com/wsdl/v2018_1_0/netsuite.wsdl',
            'newstore_url_api': 'url',
            # 'newstore_use_auth_lambda': '1',
            # 'newstore_auth_lambda': '${self:provider.tenant}-auth-token-generator-${self:provider.stage}-get_auth_token',
        }
        self.os_env = patch.dict('os.environ', self.variables)
        self.os_env.start()

        patcher_netsuite_login = patch('netsuite.service.client.service.login')
        self.patched_netsuite_login = patcher_netsuite_login.start()
        self.patched_netsuite_login.return_value = {'status': 'OK'}

        newstore_config_mock = patch('netsuite_asn_import.utils.Utils.get_newstore_config')
        self.patched_newstore_config_mock = newstore_config_mock.start()
        self.patched_newstore_config_mock.return_value = {
            "host": "url",
            "username": "username",
            "password": "password"
        }

        netsuite_config_mock = patch('netsuite_asn_import.utils.Utils.get_netsuite_config')
        self.patched_netsuite_config_mock = netsuite_config_mock.start()
        self.patched_netsuite_config_mock.return_value = {
            "transfer_order_fulfillments_saved_search_id": "customsearch_nws_store_transfer_fullfill",
            "item_fulfillment_processed_flag_script_id": "custbody_fulfillment_processed"
        }

        netsuite_location_mock = patch('netsuite_asn_import.utils.Utils.get_netsuite_location_map')
        self.patched_netsuite_location_mock = netsuite_location_mock.start()
        self.patched_netsuite_location_mock.return_value = {
            "location_1_id_nom": {"id": 1, "ff_node_id": "node_id_1"},
            "DC": {"id": 7, "ff_node_id": "DC"}
        }

        from netsuite_asn_import.aws.import_netsuite_item_fulfillments import update_newstore_asns
        self.update_newstore_asns = update_newstore_asns

    @patch('netsuite_asn_import.aws.import_netsuite_item_fulfillments.mark_imported_by_newstore', autospec=True)
    @patch('netsuite_asn_import.aws.import_netsuite_item_fulfillments.get_item_fulfillment', autospec=True)
    @patch('netsuite_asn_import.aws.import_netsuite_item_fulfillments.run_item_fulfillment_ss', autospec=True)
    @patch('requests.post', autospec=True)
    def test_import_asns(self, mock_post, mock_run_item_fulfillment_ss, mock_get_item_fulfillment,
                         mock_mark_imported_by_newstore):
        saved_search_results = TestFrankandoakASNImport._load_json_file('saved_search_results.json')
        item_fulfillment = TestFrankandoakASNImport._load_json_file('item_fulfillment.json')
        item_fulfillment['shippedDate'] = datetime(2020, 6, 16, 9, 45, 00)
        asn_transformed = TestFrankandoakASNImport._load_json_file('asn_transformed.json')

        func = asyncio.Future()
        func.set_result(saved_search_results)
        mock_run_item_fulfillment_ss.return_value = func

        func = asyncio.Future()
        func.set_result((True, item_fulfillment))
        mock_get_item_fulfillment.return_value = func

        loop_task = self.update_newstore_asns()
        TestFrankandoakASNImport._loop_wrap(loop_task)

        mock_mark_imported_by_newstore.assert_called_with(1000)
        calls = [
            call('https://url/v0/i/inventory/asns',
                 auth=ANY,
                 headers={
                    'Content-Type': 'application/json',
                    'tenant': 'frankandoak',
                    'X-AWS-Request-ID': '',
                    'User-Agent': ANY
                 },
                 data=json.dumps(asn_transformed)),
        ]
        mock_post.assert_has_calls(calls)
