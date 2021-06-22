import os
from io import StringIO
import logging
import csv
import json
import boto3
from newstore_common.aws import init_root_logger

init_root_logger(__name__)
LOGGER = logging.getLogger(__name__)

S3_BUCKET_NAME = os.environ['S3_BUCKET']
S3_OUTPUT_LOCATION = os.environ['S3_OUTPUT_LOCATION']
CSV_ROW_LIMIT = os.environ['CSV_ROW_LIMIT']
CSV_DELIMITER = os.environ['CSV_DELIMITER'] or ","

S3 = boto3.resource('s3')
S3_BUCKET = S3.Bucket(S3_BUCKET_NAME)


def split_csv_file(s3_bucket_name, s3_file_key):
    check_row_name = os.environ.get("CHECK_ROW_NAME", "")
    try:
        s3_object = S3.Object(s3_bucket_name, s3_file_key)
        csvdata = s3_object.get()['Body'].read().decode('utf-8')
        data = csv.DictReader(StringIO(csvdata, newline=None), delimiter=CSV_DELIMITER)

        current_limit = int(CSV_ROW_LIMIT)
        current_piece = 1
        current_order_id = ""
        output = StringIO()
        output_writer = csv.DictWriter(output, fieldnames=data.fieldnames, delimiter=CSV_DELIMITER)
        output_writer.writeheader()

        for i, row in enumerate(data):
            # also check order id in addition to line limit, as an order has multiple csv rows
            if i >= current_limit and (check_row_name == "" or current_order_id != row[check_row_name]):
                create_s3_file(output.getvalue(), f"{S3_OUTPUT_LOCATION}{current_piece:03}-{s3_file_key}")

                current_piece += 1
                current_limit += int(CSV_ROW_LIMIT)

                output = StringIO()
                output_writer = csv.DictWriter(output, fieldnames=data.fieldnames, delimiter=CSV_DELIMITER)
                output_writer.writeheader()

            current_order_id = row[check_row_name] if check_row_name else ""
            output_writer.writerow(row)

        # upload remaining orders when all csv rows were processed
        if output.getvalue():
            create_s3_file(output.getvalue(), f"{S3_OUTPUT_LOCATION}{current_piece:03}-{s3_file_key}")

        # Move to archive
        copy_source = {
            'Bucket': s3_bucket_name,
            'Key': s3_file_key
        }
        S3.Object(s3_bucket_name, "archive/" + s3_file_key).copy_from(CopySource=copy_source)
        s3_object.delete()

    except Exception as ex: # pylint: disable=broad-except
        LOGGER.exception(f'Error while creating CSV: {ex}.')


def create_s3_file(content, key):
    s3obj = S3_BUCKET.put_object(Key=key, Body=content)

    if s3obj:
        LOGGER.info(f'Created {s3obj}')
    else:
        LOGGER.error(f"Failed to create CSV file '{key}'")


def handler(event, _):
    LOGGER.info(f"Event: {json.dumps(event, indent=2)}")

    for record in event['Records']:
        # Get CSV from S3
        s3_bucket_name = record['s3']['bucket']['name']
        s3_file_key = record['s3']['object']['key']

        split_csv_file(s3_bucket_name, s3_file_key)

    return {
        "success": True
    }
