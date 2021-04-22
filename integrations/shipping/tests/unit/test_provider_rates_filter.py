import json
import os
import unittest
from unittest.mock import Mock

from dacite import from_dict
from shipping.app.provider_rates import get_provider_rates
from shipping.app.shipping_options_provider_rates import ProviderRatesRequest

class TestProviderRatesFilter(unittest.TestCase):

    @staticmethod
    def _load_json_file(resource_path: str, file: str):
        filepath = os.path.join(resource_path, file)
        with open(filepath) as json_content:
            return json.load(json_content)

    def setUp(self):
        self.current_path = os.path.abspath(os.path.dirname(__file__))
        self.resource_path = os.path.join(self.current_path, "./fixtures")
        response = self._load_json_file(self.resource_path, 'fulfillment_config_response.json')

    def test_filter(self):

        event = self._load_json_file(self.resource_path, 'provider_rates_request.json')
        event["bag"]["products"][0]["price"]["amount"] = 1500.0
        provider_rates_request = from_dict(data_class=ProviderRatesRequest, data=event)
        s_provider_rates = get_provider_rates(provider_rates_request)
        assert "request_id" in s_provider_rates

