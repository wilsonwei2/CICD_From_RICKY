# import os
# import json
# import unittest
#
# import boto3
#
# from unittest.mock import patch
#
#
# # Install moto if it doesn't exist
# try:
#     from moto import mock_s3
# except ImportError:
#     import pip
#     pip.main(['install', 'moto'])
#     from moto import mock_s3, mock_stepfunctions
#
# class TestHandler(unittest.TestCase):
#     @staticmethod
#     def _load_json_file(filename):
#         filepath = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', filename)
#         with open(filepath) as json_content:
#             return json.load(json_content)
#
#     @staticmethod
#     def load_csv_file_to_pricebooks():
#         with open(f'data/test_price_data_csv.csv') as csvfile:
#             price_books = csv_to_pricebooks(csvfile)
#             return price_books
#
#     def setUp(self):
#         self.variables = {
#             'S3_BUCKET': 'marine-layer-x-0-newstore-dmz',
#             'S3_PREFIX': 'import_CSVs/NWSPC/',
#             'CHUNK_SIZE': '10000',
#             'SECS_BETWEEN_CHUNKS': 'queued_for_import/',
#             'STATE_MACHINE_ARN': 'arn:aws:states:us-east-1:219627247451:stateMachine:stn-state-machine',
#         }
#         self.os_env = patch.dict('os.environ', self.variables)
#         self.os_env.start()
#
#     @mock_s3
#     @mock_stepfunctions
#     @patch('csv_price_processor.aws.csv_price_processor.csv_to_pricebooks')
#     def test_handler(self, mock_csv):
#         # To mock S3 we need to do the import here
#         from csv_price_processor.aws.csv_price_processor import handler  # pylint: disable=C0415
#         mock_csv.return_value =  {
#             'head': {
#                 'pricebook': 'msrp',
#                 'catalog': 'storefront-catalog-en',
#                 'currency': 'USD'
#             },
#             'items': [
#                 {
#                 'product_id': "1121334243-1",
#                 'value': "110.99",
#                 },
#                 {
#                 'product_id': "1121334243-2",
#                 'value': "111.99",
#                 }
#             ],
#         }
#         # event = self._load_json_file('event.json')
#         test_event = {}
#         event_item1 = {}
#         event_item2 = {}
#         test_event['Records'] = [event_item1]
#         event_item1['eventName'] = "ObjectCreated:event1_name"
#         event_item1['s3'] = {'bucket' : {'name': 'marine-layer-x-0-newstore-dmz'}, 'object': {'key': 'import_CSVs/test_price_data_csv.csv'}}
#         # event_item2['eventName'] = "ObjectCreated:event2_name"
#         # event_item1['s3'] = {'bucket': {'name': 'marine-layer-x-0-newstore-dmz'}, 'object': {'key': 'queue_for_import/prices/simplefile'}}
#         event = test_event
#
#
#         conn = boto3.resource('s3', region_name='us-east-1') # pylint: disable=no-member
#
#         definition_json = {
#             "Comment": "A Hello World example of the Amazon States Language using a Pass state",
#             "StartAt": "HelloWorld",
#             "States": {
#                 "HelloWorld": {
#                   "Type": "Pass",
#                   "Result": "Hello World!",
#                   "End": "true"
#                 }
#               }
#             }
#
#
#         step_function_client = boto3.client('stepfunctions', region_name='us-east-1')
#         step_function_client.create_state_machine(
#             name = 'step_function_test',
#             definition = json.dumps(definition_json),
#             roleArn='arn:aws:states:us-east-1:219627247451:stateMachine:stn-state-machine')
#
#
#         conn.create_bucket(Bucket='marine-layer-x-0-newstore-dmz') # pylint: disable=no-member
#
#         conn.meta.client.upload_file('data/test_price_data_csv.csv',
#                                      'marine-layer-x-0-newstore-dmz',
#                                      'import_CSVs/test_price_data_csv.csv') # pylint: disable=no-member
#
#
#         assert True if handler(event, {}) else False
