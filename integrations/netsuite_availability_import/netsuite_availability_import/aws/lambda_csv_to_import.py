import io
import os
import csv
import json
from urllib.parse import unquote
import logging
import boto3
import zipfile
from datetime import datetime
from netsuite_availability_import.utils import Utils
from newstore_adapter.connector import NewStoreConnector

REGION = os.environ['REGION']
TENANT = os.environ['TENANT']
S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']
S3_CHUNK_SIZE = os.environ['S3_CHUNK_SIZE']
S3_CHUNK_INTERVAL = os.environ['S3_CHUNK_INTERVAL']
S3_PREFIX = os.environ['S3_PREFIX']
CFR_TABLE_NAME = os.environ['CFR_TABLE']
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']
IMPORT_STORE_DATA = os.environ['IMPORT_STORE_DATA']

S3 = boto3.resource('s3')
S3_BUCKET = S3.Bucket(S3_BUCKET_NAME)
LOGGER = logging.getLogger()
LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER.setLevel(LOG_LEVEL)


def handler(event, context): # pylint: disable=W0613,too-many-locals
    """
    Load availabilities from CSV file sent by Netsuite, format data and pass to step function `s3_to_newstore` which handles Newstore import logic.
    """
    LOGGER.info(f"Event: {json.dumps(event, indent=2)}")

    items = []

    for record in event['Records']:
        # Get CSV from S3
        s3_bucket_name = record['s3']['bucket']['name']
        s3_file_key = unquote(record['s3']['object']['key'])
        LOGGER.info(f"bucket name: {s3_bucket_name}")

        try:
            obj = S3.Object(s3_bucket_name, s3_file_key)
            csvdata = obj.get()['Body'].read().decode('utf-8')
            data = csv.DictReader(io.StringIO(csvdata), delimiter=',')
            LOGGER.debug(f'csvdata - {csvdata}')

            items.extend(get_items(data))

            copy_source = {
                'Bucket': s3_bucket_name,
                'Key': s3_file_key
            }

            # Move to archive
            S3.Object(s3_bucket_name, "archive/" + s3_file_key).copy_from(CopySource=copy_source)
            obj.delete()

        except Exception as ex: # pylint: disable=broad-except
            LOGGER.exception(f'Error while reading CSV: {ex}.')

    if not items:
        LOGGER.info("No items found in CSV files")
        return {"success": False}

    # Get completed fulfillment request dynamodb table
    cfr_table = boto3.resource('dynamodb').Table(CFR_TABLE_NAME)
    cfr = cfr_table.get_item(Key={'id': 'main'})['Item']

    distribution_centres = Utils.get_instance().get_distribution_centres()
    # names_store_id_mapping = {
    #     dc: distribution_centres[dc]
    #     for dc in distribution_centres
    # }
    store_mapping = [
        {
            'fulfillment_node_id': dc_loc_id,
            'store_id': ""
        } for dc_loc_id in distribution_centres.values()
    ]

    # This is only required one time for initial migration and testing purposes
    # Add the store inventory mapping just if a preference is set to true
    if IMPORT_STORE_DATA.lower() in ('yes', 'true', '1'):
        newstore_config = Utils.get_instance().get_newstore_config()
        ns_handler = NewStoreConnector(
            tenant='frankandoak',
            context=context,
            username=newstore_config['username'],
            password=newstore_config['password'],
            host=newstore_config['host']
        )
        add_stores_to_mapping(store_mapping, ns_handler)

    LOGGER.debug(f'store_mapping: {store_mapping}')

    head = {
        'store_mapping': store_mapping,
        'completed_fulfillment_requests': {
            'logical_timestamp_start': int(cfr['last']),
            'logical_timestamp_end': int(cfr['current'])
        },
        'mode': 'atp'
    }

    # Create zips and upload them to s3
    now = datetime.utcnow()
    object_prefix = get_object_prefix(now)

    for i, chunk in enumerate(iter_chunks(items, int(S3_CHUNK_SIZE)), start=1):
        output = {'head': head, 'items': chunk}
        jsonbytes = json.dumps(output).encode('utf-8')
        output_key = f'{object_prefix}-{i:03}.zip'
        LOGGER.info(f'Zipped chunk {i}')

        data = io.BytesIO()
        output_zip = zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED)
        output_zip.writestr('availabilities.json', jsonbytes)
        output_zip.close()
        data.seek(0)
        s3_object = S3_BUCKET.put_object(Key=output_key, Body=data)
        data.close()

        LOGGER.info(f'Zipped and uploaded {s3_object}')
        LOGGER.debug(json.dumps(output, indent=2))

    # execute import step function
    step_function_response = execute_step_function(object_prefix)

    if (step_function_response is None or "startDate" not in step_function_response):
        return {"success": False}

    # Update CFR timestamps
    last_run = now.isoformat()
    cfr_table.update_item(Key={'id': 'main'},
                          UpdateExpression='SET #last = :last, last_run = :last_run',
                          ExpressionAttributeValues={':last': cfr['current'], ':last_run': last_run},
                          ExpressionAttributeNames={'#last': 'last'})
    LOGGER.debug(f'last_run: {last_run}')
    LOGGER.info(f"Last logical timestamp: {cfr['current']}")

    return {"success": True}


def iter_chunks(arr, size):
    for i in range(0, len(arr), size):
        yield arr[i:i+size]


def get_items(csv_data):
    items = []

    for item in csv_data:
        try:
            items.append({
                'fulfillment_node_id': item['Location'],
                'product_id': item['ProductSKU'],
                'quantity': int(float(item['Available'].replace(',', ''))) or 0
            })
        except KeyError as e:
            LOGGER.error(f"Error when reading inventory file {e}. Skipping {item}")

    return items


def get_object_prefix(now):
    return f"{S3_PREFIX}availabilities/{now.strftime('%Y-%m-%d')}/{now.strftime('%H:%M:%S')}"


def execute_step_function(object_prefix):
    # Step function execution
    try:
        step_function_input = json.dumps({
            "bucket": S3_BUCKET.name,
            "prefix": object_prefix,
            "chunk_prefix": S3_PREFIX,
            "secs_between_chunks": int(S3_CHUNK_INTERVAL),
            "dest_bucket": S3_BUCKET.name,
            "dest_prefix": "import_files/",
        })
        return boto3.client('stepfunctions').start_execution(stateMachineArn=STATE_MACHINE_ARN, input=step_function_input)
    except Exception as ex: # pylint: disable=broad-except
        LOGGER.exception(f"Failed to execute import step function. CSV files have already been archived. Error: {ex}")
        return None

def add_stores_to_mapping(store_mapping, ns_handler):
    # Add Stores to store mapping - only required if store inventory is imported
    locations = ns_handler.get_stores()['stores']
    for store in locations:
        store_id = None
        if 'store_id' in store:
            store_id = store['store_id']

        store_mapping.append({
            'fulfillment_node_id': store_id,
            'store_id': store_id
        })
