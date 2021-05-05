import os
import json
import boto3
import unittest
from unittest.mock import patch
from email.message import EmailMessage
from email.policy import SMTPUTF8

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
            'S3_PREFIX': 'import_CSVs/',
            'S3_BUCKET': 'mybucket'
        }
        self.os_env = patch.dict('os.environ', self.variables)
        self.os_env.start()

    @mock_s3
    def test_handler(self):
        # To mock S3 we need to do the import here
        from email_attachment_to_csv.aws.lambda_csv_from_email import handler # pylint: disable=C0415

        event = self._load_json_file('event.json')
        # We need to create the bucket and file since this is all in Moto's 'virtual' AWS account
        s3_client = boto3.client('s3', region_name='us-east-1')
        conn = boto3.resource('s3', region_name='us-east-1')
        conn.create_bucket(Bucket='mybucket')
        # Create email obj with attachment
        msg = EmailMessage()
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'fixtures', 'attachment.csv'), 'rb') as attfile:
            msg.add_attachment(attfile.read(),
                               maintype='text',
                               subtype='csv',
                               filename='attachment.csv')
        s3_client.put_object(Bucket='mybucket', Key='ses/emailfile', Body=msg.as_bytes(policy=SMTPUTF8))

        handler(event, {})

        # Check if the attachment was saved to the /import_CSVs folder
        results = s3_client.list_objects(Bucket='mybucket', Prefix='import_CSVs/attachment.csv')
        self.assertTrue('Contents' in results)
