import os
import json
import boto3
import unittest
from unittest.mock import patch

# Install moto if it doesn't exist
try:
    from moto import mock_s3
except ImportError:
    import pip
    pip.main(['install', 'moto'])
    from moto import mock_s3


class TestMarineEmailAttachmentToCSV(unittest.TestCase):
    @staticmethod
    def _load_json_file(filename):
        filepath = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'fixtures', filename)
        with open(filepath) as json_content:
            return json.load(json_content)

    def setUp(self):
        self.variables = {
            'DESTINATION_BUCKET': 'mybucket',
            'DESTINATION_PREFIX': 'import_files/'
        }
        self.os_env = patch.dict('os.environ', self.variables)
        self.os_env.start()

    @mock_s3
    def test_handler(self):
        # To mock S3 we need to do the import here
        from s3_to_newstore.aws.lambda_step_function import handler # pylint: disable=C0415

        event = self._load_json_file('event.json')
        # We need to create the bucket and file since this is all in Moto's 'virtual' AWS account
        s3_client = boto3.client('s3', region_name='us-east-1')
        conn = boto3.resource('s3', region_name='us-east-1')
        conn.create_bucket(Bucket='mybucket')
        s3_client.put_object(Bucket='mybucket', Key='queue_for_import/availabilities/simplefile', Body='simplefile')

        result = handler(event, {})
        self.assertTrue(result['continue'])

        # Check if the attachment was saved to the /import_CSVs folder
        results = s3_client.list_objects(Bucket='mybucket', Prefix='')
        self.assertTrue('Contents' in results)
