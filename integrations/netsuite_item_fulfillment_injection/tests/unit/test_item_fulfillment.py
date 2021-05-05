import unittest
from unittest.mock import patch
import os
import sys
import json
import asyncio
from zeep.helpers import serialize_object
from tests.unit.data import constants
from tests.unit.data.dev_os_env import netsuite as MOCK_NETSUITE_CONFIG


class TestItemFulfillmentProcessing(unittest.TestCase):
    @staticmethod
    def _assert_json(test_case, json1, json2):
        if isinstance(json1, dict):
            if sys.version_info >= (3, 0):
                for key, value in json1.items():
                    TestItemFulfillmentProcessing._assert_json(test_case, value, json2[key])
            else:
                for key, value in json1.iteritems():
                    TestItemFulfillmentProcessing._assert_json(test_case, value, json2[key])
        elif isinstance(json1, list):
            for i, value in enumerate(json1):
                TestItemFulfillmentProcessing._assert_json(test_case, value, json2[i])
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

        netsuite_config_mock = patch('netsuite_item_fulfillment_injection.helpers.utils.Utils.get_netsuite_config')
        self.patched_netsuite_config_mock = netsuite_config_mock.start()
        self.patched_netsuite_config_mock.return_value = MOCK_NETSUITE_CONFIG

        constants.setup_patches(self)

    def test_map_item_fulfillment_packages(self):
        fulfillment = TestItemFulfillmentProcessing._load_json_file('fulfillment_example.json')
        item_fulfillment_packages_mapped = TestItemFulfillmentProcessing._load_json_file('item_fulfillment_packages_mapped.json')

        from netsuite_item_fulfillment_injection.transformers import process_fulfillment
        result = process_fulfillment.map_item_fulfillment_packages(fulfillment)
        TestItemFulfillmentProcessing._assert_json(self, serialize_object(result), item_fulfillment_packages_mapped)

    def test_map_item_fulfillment_items(self):
        fulfillment_request = TestItemFulfillmentProcessing._load_json_file('fulfillment_request_message.json')['order']
        item_fulfillment_items_mapped = TestItemFulfillmentProcessing._load_json_file('item_fulfillment_items_mapped.json')

        from netsuite_item_fulfillment_injection.transformers import process_fulfillment
        result = process_fulfillment.map_item_fulfillment_items(fulfillment_request)
        TestItemFulfillmentProcessing._assert_json(self, serialize_object(result), item_fulfillment_items_mapped)

    def test_map_item_fulfillment_items_multi_item(self):
        fulfillment_request = TestItemFulfillmentProcessing._load_json_file('fulfillment_request_message.json')['order']
        fulfillment_request['items'].append(fulfillment_request['items'][0])
        item_fulfillment_items_mapped = TestItemFulfillmentProcessing._load_json_file('item_fulfillment_items_mapped.json')
        item_fulfillment_items_mapped[0]['quantity'] = 2

        from netsuite_item_fulfillment_injection.transformers import process_fulfillment
        result = process_fulfillment.map_item_fulfillment_items(fulfillment_request)
        TestItemFulfillmentProcessing._assert_json(self, serialize_object(result), item_fulfillment_items_mapped)
