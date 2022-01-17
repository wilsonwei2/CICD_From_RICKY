import unittest
from unittest.mock import patch, create_autospec, call, ANY, Mock
import os
import sys
import json
import requests
from datetime import date, datetime
from zeep.helpers import serialize_object

from . import common as cmn

sys.modules['netsuite.netsuite_environment_loader'] = Mock()
cmn.setup_environment_variables()


class TestUntuckitTransformProcessAdjustment(unittest.TestCase):
    def setUp(self):
        patcher_netsuite_login = patch('netsuite.service.client.service.login')
        self.patched_netsuite_login = patcher_netsuite_login.start()
        self.patched_netsuite_login.return_value = {'status': 'OK'}

        patcher_locations = patch('netsuite_adjustments_injection.helpers.util.get_nws_to_nts_locations')
        self.patched_locations = patcher_locations.start()
        self.patched_locations.return_value = {
            'newstore_location_id': {
                'id': '10', 
                'id_damage': '11', 
                'ff_node_id': '012_Boston'
            }
        }

        patcher_netsuite_config = patch('netsuite_adjustments_injection.helpers.util.get_netsuite_config')
        self.patched_netsuite_config = patcher_netsuite_config.start()
        self.patched_netsuite_config.return_value = {
            'currency_usd_internal_id': '1',
            'currency_cad_internal_id': '2',
            'currency_eur_internal_id': '3',
            'currency_gbp_internal_id': '4',
            'subsidiary_us_internal_id': '10',
            'subsidiary_ca_internal_id': '20',
            'subsidiary_uk_internal_id': '30'
        }

        from netsuite_adjustments_injection.transformers.process_adjustment import transform_inventory_transfer
        self.transform_inventory_transfer = transform_inventory_transfer

    def test_transform_inventory_transfer(self):
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'fixtures', 'event.json')) as f:
            adjustment_event = json.load(f)['payload']

        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'fixtures', 'event_transformed.json')) as f:
            expected_result = json.load(f)

        store = {'physical_address': {'country': 'US'}, 'timezone': 'America/New_York'}
        products_info = [
            {
                'netsuite_internal_id': '100',
                'quantity': 1
            }
        ]
        
        response = self.transform_inventory_transfer(adjustment_event, products_info, store)
        response = serialize_object(response)
        cmn.assert_json(self, response, expected_result)
        cmn.assert_json(self, expected_result, response)

    def test_transform_inventory_transfer_with_note(self):
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'fixtures', 'event.json')) as f:
            adjustment_event = json.load(f)['payload']
            adjustment_event['note'] = 'Damaged collar'

        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'fixtures', 'event_transformed.json')) as f:
            expected_result = json.load(f)
            expected_result['memo'] = 'Damaged - Damaged collar'

        store = {'physical_address': {'country': 'US'}, 'timezone': 'America/New_York'}
        products_info = [
            {
                'netsuite_internal_id': '100',
                'quantity': 1
            }
        ]
        
        response = self.transform_inventory_transfer(adjustment_event, products_info, store)
        response = serialize_object(response)
        cmn.assert_json(self, response, expected_result)
        cmn.assert_json(self, expected_result, response)
