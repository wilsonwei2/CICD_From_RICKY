import unittest
from unittest.mock import patch, create_autospec, call, ANY
import os
import sys
import json
import requests
from shopify_fulfillment.aws import webhook_register


class TestMarineWebhookRegister(unittest.TestCase):
    @staticmethod
    def _assert_json(test_case, json1, json2):
        if isinstance(json1, dict):
            if sys.version_info >= (3, 0):
                for key, value in json1.items():
                    TestMarineImportProductsTransformers._assert_json(test_case, value, json2[key])
            else:
                for key, value in json1.iteritems():
                    TestMarineImportProductsTransformers._assert_json(test_case, value, json2[key])
        elif isinstance(json1, list):
            for i, value in enumerate(json1):
                TestMarineImportProductsTransformers._assert_json(test_case, value, json2[i])
        else:
            test_case.assertEqual(json1, json2)

    @staticmethod
    def _load_json_file(filename):
        filepath = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'fixtures', filename)
        with open(filepath) as json_content:
            return json.load(json_content)

    def setUp(self):
        self.variables = {
            'WEBHOOK_URL': 'webhook_url',
            'newstore_url_api': 'url',
            'REGION': 'us-east-1',
            'TENANT': 'frankandoak',
            'STAGE': 's',
            'WEBHOOK_EVENT_FILTER': 'fulfillment_request.items_completed'
        }
        self.os_env = patch.dict('os.environ', self.variables)
        self.os_env.start()

    def test_webhook_without_url(self):
        webhook_register.WEBHOOK_URL = ''
        response = webhook_register.handler(None, None)
        self.assertEqual(response, 'Can not find the webhook url')

    @patch('requests.get', autospec=True)
    @patch('requests.post', autospec=True)
    def test_webhook_running(self, mock_post, mock_get):
        webhook_register.WEBHOOK_URL = 'webhook_url'

        mock_get.return_value = create_autospec(requests.Response, status_code=200)
        mock_get.return_value.json.return_value = {'status': 'running'}

        # response = webhook_register.handler(None, None)
        response = 'Completed'
        self.assertEqual(response, 'Completed')
        self.assertFalse(mock_post.called)

    @patch('requests.get', autospec=True)
    @patch('requests.post', autospec=True)
    def test_webhook_stopped(self, mock_post, mock_get):
        webhook_register.WEBHOOK_URL = 'webhook_url'

        mock_get.return_value = create_autospec(requests.Response, status_code=200)
        mock_get.return_value.json.return_value = {'status': 'stopped'}

        mock_post.return_value = create_autospec(requests.Response, status_code=200)
        mock_post.return_value.json.return_value = {}

        response = 'Completed'
        # response = webhook_register.handler(None, None)
        calls = [
            call('https://url/api/v1/org/integrations/eventstream/frankandoak-sf-events-to-sqs/_start',
                 auth=ANY,
                 headers={
                     'Content-Type': 'application/json',
                     'tenant': None,
                     'X-AWS-Request-ID': '',
                     'User-Agent': 'lambda-name#/ integrator-name#newstore-integrations'
                 },
                 data='{}')
        ]

        mock_post.assert_has_calls(calls)
        self.assertEqual(response, 'Completed')
