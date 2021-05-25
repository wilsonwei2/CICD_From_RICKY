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
import botocore
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
SECS_BETWEEN_CHUNKS = os.environ['SECS_BETWEEN_CHUNKS']
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']

LOGGER = logging.getLogger()

def iter_chunks(arr, size):
    """
    Create chunks from CSV File
    """
    for i in range(0, len(arr), size):
        yield arr[i:i+size]


def handler(event, context):
    records_to_process = find_records(event['Records'])
    process_records(records_to_process)

def find_records(records):
    """
    Find records to process. There needs to exist a RET and a SAL pricebook.
    """
    records_to_process = []

    for record in records:
        assert record['eventName'].startswith('ObjectCreated:')
        splitted_key = record['s3']['object']['key'].split('/')
        file_name = splitted_key[-1]
        obj_path = '/'.join(splitted_key[:-1])

        matcher = re.search(r'^([a-zA-Z0-9]*)_([A-Z]{3})_([A-Z]{3})_(\d{8})\.csv$', file_name)
        if not matcher:
            LOGGER.error(f'invalid file name: {file_name} - skipping')
            continue
        prefix, currency, type, timestamp = matcher.groups()

        record_dict = {
            'bucket_name': record['s3']['bucket']['name'],
            'object_key': record['s3']['object']['key'],
            'currency': currency,
        }

        LOGGER.debug(f'found {json.dumps(record_dict)}')

        alternate_type = 'RET' if type == 'SAL' else 'SAL'
        alternate_obj_key = f'{obj_path}/{prefix}_{currency}_{alternate_type}_{timestamp}.csv'
        found_alternate = False
        try:
            alternate_obj = S3.Bucket(record_dict['bucket_name']).Object(alternate_obj_key) # pylint: disable=no-member
            alternate_obj.get()
            found_alternate = True
        except botocore.exceptions.ClientError:
            pass

        if found_alternate:
            alternate_record_dict = {
                'bucket_name': record_dict['bucket_name'],
                'object_key': alternate_obj_key,
                'currency': currency,
            }
            records_to_process.append(record_dict if type == 'RET' else alternate_record_dict)
            records_to_process.append(record_dict if type == 'SAL' else alternate_record_dict)

    LOGGER.info(records_to_process)
    return records_to_process

def process_records(records):
    """
    Reads the data from the CSV File and transforms into Newstore Pricebook
    Format and triggers the step function required to start the import jobs.
    """
    for record in records:
        s3_bucket_name = record['bucket_name']
        s3_key = record['object_key']

        currency = record['currency']

        ## This is the key step that converts the imported file
        # into our format and gives the price books back.
        s3_Object = S3.Bucket(s3_bucket_name).Object(s3_key) # pylint: disable=no-member
        LOGGER.info(f'processing {s3_key}')
        with io.TextIOWrapper(io.BytesIO(s3_Object.get()['Body'].read()), encoding='utf-8') \
                as csvfile:
            price_book = csv_to_pricebooks(csvfile, currency, 'storefront-catalog-en')

        # also import CAD prices to storefront-catalog-fr
        price_book_catalog_fr = None
        if currency == 'CAD':
            with io.TextIOWrapper(io.BytesIO(s3_Object.get()['Body'].read()), encoding='utf-8') \
                    as csvfile:
                price_book_catalog_fr = csv_to_pricebooks(csvfile, currency, 'storefront-catalog-fr') if currency == 'CAD' else None

        now = datetime.utcnow()

        time_stamp = f"{now.strftime('%Y-%m-%d')}/{now.strftime('%H:%M:%S')}"
        obj_prefix = f"{S3_PREFIX}prices/{'msrp'}/{time_stamp}"
        LOGGER.info(f'S3_PREFIX is {S3_PREFIX}')
        LOGGER.info(f'obj_prefx is {obj_prefix}')

        no_of_chunks = generate_chunks(price_book, obj_prefix)
        if price_book_catalog_fr:
            generate_chunks(price_book_catalog_fr, obj_prefix, no_of_chunks)

        copy_source = {
            'Bucket': s3_bucket_name,
            'Key': s3_key
        }

        # Move to archive
        S3.Object(s3_bucket_name, 'archive/' + s3_key).copy_from(CopySource=copy_source) # pylint: disable=no-member
        s3_Object.delete()

        # Start import step function
        input = json.dumps({
            'bucket': S3_BUCKET.name,
            'prefix': obj_prefix,
            'chunk_prefix': S3_PREFIX,
            'secs_between_chunks': int(SECS_BETWEEN_CHUNKS),
            'dest_bucket': S3_BUCKET.name,
            'dest_prefix': 'import_files/',
        })
        STEP_FUNCTION_CLIENT.start_execution(stateMachineArn=STATE_MACHINE_ARN, input=input)

def generate_chunks(price_book, obj_prefix, add_idx = 0):
    chunks = 0
    for i, chunk in enumerate(iter_chunks(price_book['items'], CHUNK_SIZE), start=1):
        out = {'head': price_book['head'], 'items': chunk}
        jsonbytes = json.dumps(out).encode('utf-8')

        idx = add_idx + i

        key = f'{obj_prefix}-{idx:03}.zip'
        LOGGER.info(f'key is {obj_prefix}')
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
