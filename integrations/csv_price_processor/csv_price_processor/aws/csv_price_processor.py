"""
price_import_processor.py

Reads the data from CSV and passes to transform,
used the response data to create the price books

Trigger multiple price books using step functions.
"""
import logging
import os
import io
import json
import boto3
import zipfile as zf

from urllib.parse import unquote
from datetime import datetime


## Introduced namespaces ..
## Package namespaces
## Look into it.
from csv_price_processor.aws.transformer import csv_to_pricebooks

STEP_FUNCTION_CLIENT = boto3.client('stepfunctions', 'us-east-1')
S3 = boto3.resource('s3')
S3_BUCKET = S3.Bucket(os.environ['S3_BUCKET']) # pylint: disable=no-member
S3_PREFIX = os.environ['S3_PREFIX']
CHUNK_SIZE = int(os.environ['CHUNK_SIZE'])
SECS_BETWEEN_CHUNKS = os.environ["SECS_BETWEEN_CHUNKS"]
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

def iter_chunks(arr, size):
    """
    Create chunks from CSV File
    """
    for i in range(0, len(arr), size):
        yield arr[i:i+size]


def handler(event, context):
    """
    Reads the data from the CSV File and transforms into Newstore Pricebook
    Format and triggers the step function required to start the import jobs.
    """
    for record in event['Records']:
        assert record['eventName'].startswith('ObjectCreated:')

        s3_bucket_name = record['s3']['bucket']['name']
        s3_key = record['s3']['object']['key']

        ## This is the key step that converts the imported file
        # into our format and gives the price books back.
        s3_Object = S3.Bucket(s3_bucket_name).Object(s3_key) # pylint: disable=no-member
        with io.TextIOWrapper(io.BytesIO(s3_Object.get()['Body'].read()), encoding='utf-8') \
                as csvfile:
            price_book = csv_to_pricebooks(csvfile)

            now = datetime.utcnow()

            time_stamp = f"{now.strftime('%Y-%m-%d')}/{now.strftime('%H:%M:%S')}"
            obj_prefix = f"{S3_PREFIX}prices/{'msrp'}/{time_stamp}"
            for i, chunk in enumerate(iter_chunks(price_book['items'], CHUNK_SIZE), start=1):
                out = {'head': price_book['head'], 'items': chunk}
                jsonbytes = json.dumps(out).encode('utf-8')

                key = f"{obj_prefix}-{i:03}.zip"
                LOGGER.debug(f'Zipping chunk {i}')
                data = io.BytesIO()
                outzip = zf.ZipFile(data, 'w', zf.ZIP_DEFLATED)
                outzip.writestr('prices.json', jsonbytes)
                outzip.close()
                data.seek(0)
                s3obj = S3_BUCKET.put_object(Key=key, Body=data)
                data.close()
                LOGGER.info(f'Zipped and uploaded {s3obj}')
                LOGGER.debug(json.dumps(out, indent=2))

            # Start import step function
            input = f'{{"bucket": "{S3_BUCKET.name}",' \
                    f' "prefix": "{obj_prefix}", ' \
                    f'"chunk_prefix": "{S3_PREFIX}", ' \
                    f'"secs_between_chunks": {SECS_BETWEEN_CHUNKS}}}'
            STEP_FUNCTION_CLIENT.start_execution(stateMachineArn=STATE_MACHINE_ARN, input=input)
