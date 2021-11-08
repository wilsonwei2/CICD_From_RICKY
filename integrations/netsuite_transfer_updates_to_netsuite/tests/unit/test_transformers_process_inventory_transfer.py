import unittest
from unittest.mock import patch, Mock
import os
import sys
import json
import requests
import asyncio
from zeep.helpers import serialize_object

sys.modules['netsuite.netsuite_environment_loader'] = Mock()


class TestFrankAndOakTransformProcessInventoryTransfer(unittest.TestCase):
    @staticmethod
    def _assert_json(test_case, json1, json2):
        if isinstance(json1, dict):
            if sys.version_info >= (3, 0):
                for key, value in json1.items():
                    TestFrankAndOakTransformProcessInventoryTransfer._assert_json(test_case, value, json2[key])
            else:
                for key, value in json1.iteritems():
                    TestFrankAndOakTransformProcessInventoryTransfer._assert_json(test_case, value, json2[key])
        elif isinstance(json1, list):
            for i, value in enumerate(json1):
                TestFrankAndOakTransformProcessInventoryTransfer._assert_json(test_case, value, json2[i])
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
            'netsuite_wsdl_url': 'https://webservices.netsuite.com/wsdl/v2018_1_0/netsuite.wsdl',
            'PHYSICAL_GC_ID': 'PGC',
            'PHYSICAL_GC_SKU': '5500000-000',
        }
        self.os_env = patch.dict('os.environ', self.variables)
        self.os_env.start()

        patcher_netsuite_login = patch('netsuite.service.client.service.login')
        self.patched_netsuite_login = patcher_netsuite_login.start()
        self.patched_netsuite_login.return_value = {'status': 'OK'}

        newstore_config_mock = patch('netsuite_transfer_updates_to_netsuite.helpers.utils.Utils.get_newstore_config')
        self.patched_newstore_config_mock = newstore_config_mock.start()
        self.patched_newstore_config_mock.return_value = {
            "host": "url",
            "username": "username",
            "password": "password"
        }

        netsuite_config_mock = patch('netsuite_transfer_updates_to_netsuite.helpers.utils.Utils.get_netsuite_config')
        self.patched_netsuite_config_mock = netsuite_config_mock.start()
        self.patched_netsuite_config_mock.return_value = {
            'currency_usd_internal_id': '1',
            'currency_cad_internal_id': '2',
            'currency_eur_internal_id': '3',
            'currency_gbp_internal_id': '4',
            'subsidiary_us_internal_id': '10',
            'subsidiary_ca_internal_id': '20',
            'subsidiary_uk_internal_id': '30',
            'item_receipt_custom_form': '40'
        }

        netsuite_location_mock = patch('netsuite_transfer_updates_to_netsuite.helpers.utils.Utils.get_netsuite_location_map')
        self.patched_netsuite_location_mock = netsuite_location_mock.start()
        self.patched_netsuite_location_mock.return_value = {
            'newstore_location_id': {
                'id': '10',
                'id_damage': '11',
                'ff_node_id': '012_Boston'
            }
        }

        import netsuite_transfer_updates_to_netsuite.transformers.process_inventory_transfer as pit
        self.pit = pit

    def test_transform_inventory_transfer(self):
        event = self._load_json_file('event.json')['payload']
        store = self._load_json_file('store.json')
        item_fulfillment = self._load_json_file('netsuite_item_fulfillment.json')
        expected_result = self._load_json_file('event_transformed.json')

        loop_task = self.pit.create_item_receipt(item_fulfillment, event, store)

        item_receipt, inventory_adjustment = self._loop_wrap(loop_task)
        item_receipt = serialize_object(item_receipt)
        item_receipt['tranDate'] = item_receipt['tranDate'].isoformat()

        self._assert_json(self, item_receipt, expected_result)
        self._assert_json(self, expected_result, item_receipt)
        self.assertEqual(inventory_adjustment, None)

    def test_transform_inventory_transfer_map_received_items(self):
        event = self._load_json_file('event.json')['payload']
        item_fulfillment = self._load_json_file('netsuite_item_fulfillment.json')
        expected_result = self._load_json_file('items_transformed.json')

        loop_task = self.pit.map_received_items(event.get('items', []),
                                                '10',
                                                item_fulfillment['itemList']['item'])

        received_items, overage_items = self._loop_wrap(loop_task)
        received_items = serialize_object(received_items)

        self._assert_json(self, received_items, expected_result)
        self._assert_json(self, expected_result, received_items)
        self.assertEqual(overage_items, [])

    def test_replace_pgc_product_id(self):
        test_message = {
                "asn_id": "f329f3dc-005a-4869-9064-54a1eb1fd99c",
                "associate_id": "20467196ac8459928978b08408041fd6",
                "chunk_number": 1,
                "fulfillment_location_id": "TOST",
                "id": "30df6d55-355b-4f59-a841-7764c4e8a88f",
                "items": [
                    {
                        "external_identifiers": {
                            "sku": "PGC"
                        },
                        "product_id": "PGC",
                        "quantity": 5
                    },
                                    {
                        "external_identifiers": {
                            "sku": "PGC"
                        },
                        "product_id": "123123",
                        "quantity": 5
                    }
                ],
                "order_ref": "TO0005593",
                "processed_at": "2021-10-18T08:25:09.717Z",
                "published_at": "2021-10-18T08:25:55.185Z",
                "shipment_ref": "IF0525547 - abcdef",
                "stock_location_name": "main",
                "total_chunks": 1
            }

        expected_result = {
                "asn_id": "f329f3dc-005a-4869-9064-54a1eb1fd99c",
                "associate_id": "20467196ac8459928978b08408041fd6",
                "chunk_number": 1,
                "fulfillment_location_id": "TOST",
                "id": "30df6d55-355b-4f59-a841-7764c4e8a88f",
                "items": [
                    {
                        "external_identifiers": {
                            "sku": "PGC"
                        },
                        "product_id": "5500000-000",
                        "quantity": 5
                    },
                                    {
                        "external_identifiers": {
                            "sku": "PGC"
                        },
                        "product_id": "123123",
                        "quantity": 5
                    }
                ],
                "order_ref": "TO0005593",
                "processed_at": "2021-10-18T08:25:09.717Z",
                "published_at": "2021-10-18T08:25:55.185Z",
                "shipment_ref": "IF0525547 - abcdef",
                "stock_location_name": "main",
                "total_chunks": 1
            }

        items_received_event = self.pit.replace_pgc_product_id(test_message, 'PGC', '5500000-000')

        assert items_received_event == expected_result
