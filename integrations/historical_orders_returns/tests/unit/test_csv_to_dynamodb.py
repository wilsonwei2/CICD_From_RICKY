import json
import boto3
import csv
from io import StringIO
from moto import mock_s3, mock_dynamodb2


@mock_s3
@mock_dynamodb2
def test_csv_to_dynamodb(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("CSV_DELIMITER", ",")
    monkeypatch.setenv("TYPE", "order")

    # create bucket
    S3 = boto3.resource("s3", region_name="us-east-1")
    bucket = S3.create_bucket(Bucket="testbucket")
    s3_client = boto3.client('s3', region_name='us-east-1')

    # create test file
    input_file = open("data/input/single_order.csv", "r")
    input_string = input_file.read()
    bucket.put_object(Key="single_order.csv", Body=input_string)

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'RANGE'},
            {'AttributeName': 'status', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'},
            {'AttributeName': 'status', 'AttributeType': 'S'}
        ])

    # mock event
    event = {
        "Records": [{
            "s3": {
                "bucket": {
                    "name": "testbucket"
                },
                "object": {
                    "key": "single_order.csv"
                }
            }
        }]
    }

    from historical_orders_returns.lambdas.csv_to_dynamodb import handler
    result = handler(event, None)

    # assert successful function execution
    assert result["success"]

    # check if order is in dynamodb
    order = table.get_item(Key={'order_id': '1101689774', 'status': 'new'})['Item']
    order_payload = json.loads(order["payload"])
    assert order_payload["details"]["Name"] == "1101689774"
    assert float(order_payload["payment"]["Transaction Amount"]) == 120.69

    # check if file has been archived
    archived_files = s3_client.list_objects_v2(Bucket="testbucket", Prefix="archive/")
    assert len(archived_files["Contents"]) == 1

@mock_s3
@mock_dynamodb2
def test_csv_to_dynamodb_gc_payment(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("CSV_DELIMITER", ",")
    monkeypatch.setenv("TYPE", "order")

    # create bucket
    S3 = boto3.resource("s3", region_name="us-east-1")
    bucket = S3.create_bucket(Bucket="testbucket")
    s3_client = boto3.client('s3', region_name='us-east-1')

    # create test file
    input_file = open("data/input/single_order_gc_payment.csv", "r")
    input_string = input_file.read()
    bucket.put_object(Key="single_order_gc_payment.csv", Body=input_string)

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'RANGE'},
            {'AttributeName': 'status', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'},
            {'AttributeName': 'status', 'AttributeType': 'S'}
        ])

    # mock event
    event = {
        "Records": [{
            "s3": {
                "bucket": {
                    "name": "testbucket"
                },
                "object": {
                    "key": "single_order_gc_payment.csv"
                }
            }
        }]
    }

    from historical_orders_returns.lambdas.csv_to_dynamodb import handler
    result = handler(event, None)

    # assert successful function execution
    assert result["success"]

    # check if order is in dynamodb
    order = table.get_item(Key={'order_id': '1101285272', 'status': 'new'})['Item']
    order_payload = json.loads(order["payload"])
    print(order_payload)
    assert order_payload["details"]["Name"] == "1101285272"
    assert order_payload["payment"] == {}
    assert float(order_payload["giftcard_payment"]["Transaction Amount"]) == 122.08

    # check if file has been archived
    archived_files = s3_client.list_objects_v2(Bucket="testbucket", Prefix="archive/")
    assert len(archived_files["Contents"]) == 1

@mock_s3
@mock_dynamodb2
def test_csv_to_dynamodb_ignore_location(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("CSV_DELIMITER", ",")
    monkeypatch.setenv("TYPE", "order")

    # create bucket
    S3 = boto3.resource("s3", region_name="us-east-1")
    bucket = S3.create_bucket(Bucket="testbucket")
    s3_client = boto3.client('s3', region_name='us-east-1')

    # create test file
    input_file = open("data/input/single_order_wrong_location.csv", "r")
    input_string = input_file.read()
    bucket.put_object(Key="single_order_wrong_location.csv", Body=input_string)

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'RANGE'},
            {'AttributeName': 'status', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'},
            {'AttributeName': 'status', 'AttributeType': 'S'}
        ])

    # mock event
    event = {
        "Records": [{
            "s3": {
                "bucket": {
                    "name": "testbucket"
                },
                "object": {
                    "key": "single_order_wrong_location.csv"
                }
            }
        }]
    }

    from historical_orders_returns.lambdas.csv_to_dynamodb import handler
    result = handler(event, None)

    # assert successful function execution
    assert result["success"]

    # check if order is in dynamodb
    order = table.get_item(Key={'order_id': '1101284380', 'status': 'new'}).get('Item', None)
    assert not order

    # check if file has been archived
    archived_files = s3_client.list_objects_v2(Bucket="testbucket", Prefix="archive/")
    assert len(archived_files["Contents"]) == 1
