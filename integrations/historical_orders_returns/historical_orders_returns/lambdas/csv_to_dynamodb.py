import os
from io import StringIO
import logging
import csv
import json
import boto3
from newstore_common.aws import init_root_logger

init_root_logger(__name__)
LOGGER = logging.getLogger(__name__)

CSV_DELIMITER = os.environ['CSV_DELIMITER'] or ","
ORDERS_TABLE_NAME = os.environ['ORDERS_TABLE_NAME']
RETURNS_TABLE_NAME = os.environ['RETURNS_TABLE_NAME']

S3 = boto3.resource('s3')

DYNAMODB = boto3.resource('dynamodb', region_name='us-east-1')
ORDERS_TABLE = DYNAMODB.Table(ORDERS_TABLE_NAME)
RETURNS_TABLE = DYNAMODB.Table(RETURNS_TABLE_NAME)


def process_orders_csv_file(s3_bucket_name, s3_file_key):
    try:
        obj = S3.Object(s3_bucket_name, s3_file_key)
        data = get_csv_data(obj)

        order_obj = get_new_order_obj()
        current_order_id = ""

        for i, row in enumerate(data):
            # if row has new order id, send order to Dynamodb and create new object
            if i > 0 and current_order_id and row["Name"] != current_order_id:
                add_order_to_dynamodb(order_obj, current_order_id)
                order_obj = get_new_order_obj()

            current_order_id = row["Name"]

            # remove empty values from row
            row = dict((key, value) for key, value in row.items() if value and value.strip())

            # use specific row attributes to identify the content of the row
            if "Processed At" in row: # general order details
                order_obj["details"] = row
            elif "Lineitem name" in row: # items
                order_obj["items"].append(row)
            elif "Transaction Kind" in row and row["Transaction Kind"] == "capture": # payment
                order_obj["payment"] = row
            elif "Shipping Line Price" in row: # shipping
                order_obj["shipping"] = row

        # send last order to DynamoDB after last row was processed
        if order_obj:
            add_order_to_dynamodb(order_obj, current_order_id)

        move_to_archive(obj, s3_bucket_name, s3_file_key)

    except Exception as ex: # pylint: disable=broad-except
        LOGGER.exception(f'Error while reading CSV: {ex}.')


def process_returns_csv_file(s3_bucket_name, s3_file_key):
    try:
        obj = S3.Object(s3_bucket_name, s3_file_key)
        data = get_csv_data(obj)

        for row in data:
            if row["items"]:
                row["items"] = json.loads(row["items"])
            if row["returned_from"]:
                row["returned_from"] = json.loads(row["returned_from"])
            add_return_to_dynamodb(row, row['rma_id'])

        move_to_archive(obj, s3_bucket_name, s3_file_key)

    except Exception as ex: # pylint: disable=broad-except
        LOGGER.exception(f'Error while reading CSV: {ex}.')


def get_new_order_obj():
    return {
        "details": {},
        "items": [],
        "shipping": {},
        "payment": {}
    }

def get_csv_data(s3_object):
    csvdata = s3_object.get()['Body'].read().decode('utf-8')
    return csv.DictReader(StringIO(csvdata), delimiter=CSV_DELIMITER)

def move_to_archive(s3_object, s3_bucket_name, s3_file_key):
    # Move to archive
    copy_source = {
        'Bucket': s3_bucket_name,
        'Key': s3_file_key
    }
    S3.Object(s3_bucket_name, "archive/" + s3_file_key).copy_from(CopySource=copy_source)
    s3_object.delete()


def add_order_to_dynamodb(order, order_id):
    item = {
        'order_id': order_id,
        'payload': json.dumps(order),
        'status': 'new'
    }
    res = ORDERS_TABLE.put_item(Item=item)

    if not res:
        LOGGER.error(f"Failed to add order {order_id} to DynamoDB table.")


def add_return_to_dynamodb(return_data, rma_id):
    item = {
        'rma_id': rma_id,
        'payload': json.dumps(return_data),
        'status': 'new'
    }
    res = RETURNS_TABLE.put_item(Item=item)

    if not res:
        LOGGER.error(f"Failed to add return {rma_id} to DynamoDB table.")


def handler(event, _):
    LOGGER.info(f"Event: {json.dumps(event, indent=2)}")
    process_type = os.environ["TYPE"]

    for record in event['Records']:
        # Get CSV from S3
        s3_bucket_name = record['s3']['bucket']['name']
        s3_file_key = record['s3']['object']['key']

        if process_type == "order":
            process_orders_csv_file(s3_bucket_name, s3_file_key)
        elif process_type == "return":
            process_returns_csv_file(s3_bucket_name, s3_file_key)

    return {
        "success": True
    }
