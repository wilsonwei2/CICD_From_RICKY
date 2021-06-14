import unittest
from unittest.mock import patch
import os
import sys
import json
import datetime
from jsonschema import validate
from shopify_import_order.handlers.utils import Utils


class TestFrankandoakImportOrderTransformer(unittest.TestCase):
    @staticmethod
    def _assert_json(test_case, json1, json2):
        if isinstance(json1, dict):
            if sys.version_info >= (3, 0):
                for key, value in json1.items():
                    TestFrankandoakImportOrderTransformer._assert_json(test_case, value, json2[key])
            else:
                for key, value in json1.iteritems():
                    TestFrankandoakImportOrderTransformer._assert_json(test_case, value, json2[key])
        elif isinstance(json1, list):
            for i, value in enumerate(json1):
                TestFrankandoakImportOrderTransformer._assert_json(test_case, value, json2[i])
        else:
            test_case.assertEqual(json1, json2)

    @staticmethod
    def _load_json_file(filename):
        filepath = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'fixtures', filename)
        with open(filepath) as json_content:
            return json.load(json_content)

    def setUp(self):
        Utils.get_instance().shopify_service_level_map = {
            "standard shipping": "UPS_SUREPOST",
            "generic shipping": "UPS_GROUND"
        }
        from shopify_import_order.orders import transform
        from shopify_import_order.aws.process import _get_refund
        self.transform = transform
        self._get_refund = _get_refund

    def test_transform(self):
        order = self._load_json_file('shopify_order_webhook.json')
        transactions = self._load_json_file('shopify_order_transactions.json')['transactions']
        order_transformed = self._load_json_file('order_transformed.json')
        order_schema = self._load_json_file('order_schema.json')

        response = self.transform(transactions, order, False, 'test-shop')

        self._assert_json(self, response, order_transformed)
        self._assert_json(self, order_transformed, response)

        try:
            validate(response, order_schema)
        except Exception as ex:
            raise self.failureException('{} raised'.format(ex))

    def test_get_refund(self):
        refunds = self._load_json_file('shopify_order_refunds.json')['refunds']
        refund_returned = self._load_json_file('refund_returned.json')
        order_date = datetime.datetime.strptime('2021-03-25T12:46:44-07:00', "%Y-%m-%dT%H:%M:%S%z")

        response = self._get_refund(refunds, order_date)

        self._assert_json(self, response, refund_returned)
        self._assert_json(self, refund_returned, response)
