import unittest
import os
import sys
import json
from . import common as cmn

from unittest.mock import patch, call, ANY, Mock

sys.modules['netsuite.netsuite_environment_loader'] = Mock()
cmn.setup_environment_variables()


class TestUntuckitProcessEvent(unittest.TestCase):
    def setUp(self):
        patcher_netsuite_login = patch('netsuite.service.client.service.login')
        self.patched_netsuite_login = patcher_netsuite_login.start()
        self.patched_netsuite_login.return_value = {'status': 'OK'}

        from netsuite_adjustments_injection.aws.process_event import get_store_and_products_from_nom
        self.get_store_and_products_from_nom = get_store_and_products_from_nom


    @patch('netsuite_adjustments_injection.helpers.util.get_product', autospec=True)
    @patch('netsuite_adjustments_injection.helpers.util.get_store', autospec=True)
    @patch('netsuite_adjustments_injection.helpers.util.get_nws_location_id', autospec=True)
    def test_get_store_and_products_from_nom(self, mock_get_nws_location_id, mock_get_store, mock_get_product):
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'fixtures', 'event.json')) as f:
            event = json.load(f)['payload']

        store = {'catalog': 'storefront-catalog-en', 'locale': 'en-us'}
        mock_get_nws_location_id.return_value = 'StoreID'
        mock_get_store.return_value = store
        mock_get_product.return_value = {'extended_attributes':[{'name': 'variant_nsid', 'value': '100'}]}

        expected_result = (
            store,
            [
                {
                    'netsuite_internal_id': '100',
                    'quantity': 1
                }
            ]
        )

        response = self.get_store_and_products_from_nom(event['items'], event['fulfillment_node_id'])

        cmn.assert_json(self, response, expected_result)
        cmn.assert_json(self, expected_result, response)
