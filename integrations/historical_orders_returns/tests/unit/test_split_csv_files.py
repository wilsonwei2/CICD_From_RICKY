import json
import boto3
import csv
from io import StringIO
from moto import mock_s3


@mock_s3
def test_split_csv_files(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("S3_BUCKET", "testbucket")
    monkeypatch.setenv("S3_OUTPUT_LOCATION", "output/")
    monkeypatch.setenv("CSV_ROW_LIMIT", "100")
    monkeypatch.setenv("CSV_DELIMITER", ",")
    monkeypatch.setenv("CHECK_ROW_NAME", "Name")

    # create bucket
    S3 = boto3.resource("s3", region_name="us-east-1")
    bucket = S3.create_bucket(Bucket="testbucket")
    s3_client = boto3.client('s3', region_name='us-east-1')

    # create test file
    input_file = open("data/input/orders.csv", "r")
    input_string = input_file.read()
    bucket.put_object(Key="orders.csv", Body=input_string)

    # mock event
    event = {
        "Records": [{
            "s3": {
                "bucket": {
                    "name": "testbucket"
                },
                "object": {
                    "key": "orders.csv"
                }
            }
        }]
    }

    from historical_orders_returns.lambdas.split_csv_files import handler
    result = handler(event, None)

    # assert successful function execution
    assert result["success"]

    # check number of splitted files
    splitted_files = s3_client.list_objects_v2(Bucket="testbucket", Prefix="output/")
    assert len(splitted_files["Contents"]) == 7

    # check first file if it has expected number of entries
    obj = S3.Object("testbucket", "output/001-orders.csv")
    csvdata = obj.get()['Body'].read().decode('utf-8')
    assert len(list(csv.DictReader(StringIO(csvdata), delimiter=","))) == 109

    # check if initial file has been archived
    archived_files = s3_client.list_objects_v2(Bucket="testbucket", Prefix="archive/")
    assert len(archived_files["Contents"]) == 1
