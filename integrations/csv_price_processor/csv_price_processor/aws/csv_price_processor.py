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
import re

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

        file_name = s3_key.split("/")[-1]
        matcher = re.search(r"^[[a-zA-Z0-9]*_([A-Z]{3})_\d{8}\.csv$", file_name)
        if not matcher:
            LOGGER.error(f'invalid file name: {file_name} - skipping')
            continue
        currency = matcher.group(1)

        ## This is the key step that converts the imported file
        # into our format and gives the price books back.
        s3_Object = S3.Bucket(s3_bucket_name).Object(s3_key) # pylint: disable=no-member
        LOGGER.info(f'processing {s3_key}')
        with io.TextIOWrapper(io.BytesIO(s3_Object.get()['Body'].read()), encoding='utf-8') \
                as csvfile:
            price_book = csv_to_pricebooks(csvfile, currency, 'storefront-catalog-en')

            # also import CAD prices to storefront-catalog-fr
            price_book_catalog_fr = csv_to_pricebooks(csvfile, currency, 'storefront-catalog-fr') if currency == 'CAD' else None

            now = datetime.utcnow()

            time_stamp = f"{now.strftime('%Y-%m-%d')}/{now.strftime('%H:%M:%S')}"
            obj_prefix = f"{S3_PREFIX}prices/{'msrp'}/{time_stamp}"
            LOGGER.info(f"S3_PREFIX is {S3_PREFIX}")
            LOGGER.info(f"obj_prefx is {obj_prefix}")

            no_of_chunks = generate_chunks(price_book, obj_prefix)
            if price_book_catalog_fr:
                generate_chunks(price_book, obj_prefix, no_of_chunks)

            # Start import step function
            input = json.dumps({
                "bucket": S3_BUCKET.name,
                "prefix": obj_prefix,
                "chunk_prefix": S3_PREFIX,
                "secs_between_chunks": int(SECS_BETWEEN_CHUNKS),
                "dest_bucket": S3_BUCKET.name,
                "dest_prefix": "import_files/",
            })
            STEP_FUNCTION_CLIENT.start_execution(stateMachineArn=STATE_MACHINE_ARN, input=input)

def generate_chunks(price_book, obj_prefix, add_idx = 0):
    chunks = 0
    for i, chunk in enumerate(iter_chunks(price_book['items'], CHUNK_SIZE), start=1):
        out = {'head': price_book['head'], 'items': chunk}
        jsonbytes = json.dumps(out).encode('utf-8')

        idx = add_idx + i

        key = f"{obj_prefix}-{idx:03}.zip"
        LOGGER.info(f"key is {obj_prefix}")
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

        chunks = chunks + 1

    return chunks
