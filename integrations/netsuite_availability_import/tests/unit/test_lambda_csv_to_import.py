import os
import io
import zipfile
import json
import boto3
from datetime import datetime

# Install moto if it doesn't exist
try:
    from moto import mock_s3, mock_dynamodb2, mock_ssm
except ImportError:
    import pip
    pip.main(['install', 'moto'])
    from moto import mock_s3, mock_dynamodb2, mock_ssm


def mock_execute_step_function(_):
    return {
        'executionArn': 'string',
        'startDate': datetime(2015, 1, 1)
    }

def mock_get_object_prefix(_):
    return "test"

def _load_json_file(filename):
    filepath = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'fixtures', filename)
    with open(filepath) as json_content:
        return json.load(json_content)


@mock_s3
@mock_dynamodb2
@mock_ssm
def test_handler(monkeypatch):
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("CFR_TABLE", "CFRTable")
    monkeypatch.setenv("S3_BUCKET_NAME", "testbucket")
    monkeypatch.setenv("S3_CHUNK_INTERVAL", "30")
    monkeypatch.setenv("S3_CHUNK_SIZE", "1000")
    monkeypatch.setenv("S3_PREFIX", "queued_for_import/")
    monkeypatch.setenv("STATE_MACHINE_ARN", "")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("IMPORT_STORE_DATA", "false")

    monkeypatch.setattr("netsuite_availability_import.aws.lambda_csv_to_import.execute_step_function", mock_execute_step_function)
    monkeypatch.setattr("netsuite_availability_import.aws.lambda_csv_to_import.get_object_prefix", mock_get_object_prefix)

    event = _load_json_file('event.json')

    # Create S3
    s3_client = boto3.client('s3', region_name='us-east-1')
    conn = boto3.resource('s3', region_name='us-east-1')
    conn.create_bucket(Bucket='testbucket')

    # Put CSV file in S3
    with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'fixtures', 'input.csv'), 'rb') as attfile:
        s3_client.put_object(Bucket='testbucket', Key='import_CSVs/input.csv', Body=attfile.read())

    # Create DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(TableName="CFRTable",
        KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'id', 'AttributeType': 'S'}])
    item = {
        'id': 'main',
        'last_run': '2019-01-01T12:00:00.000Z',
        'last': '1550001641531',
        'current': '1550001641531'
    }
    table.put_item(Item=item)

    # prepare ssm
    ssm = boto3.client('ssm', "us-east-1")
    ssm.put_parameter(
        Name="/frankandoak/x/distribution_centres",
        Value=json.dumps({'MTLDC1': 'MTLDC1'}),
        Type="String"
    )

    from netsuite_availability_import.aws.lambda_csv_to_import import handler
    result = handler(event, {})

    assert result == {"success": True}

    expected_output = _load_json_file('output.json')

    # get output zip
    s3_obj = s3_client.get_object(Bucket="testbucket", Key="test-001.zip")
    with io.BytesIO(s3_obj["Body"].read()) as body:
        body.seek(0)
        # Read the file as a zipfile and process the members
        with zipfile.ZipFile(body, mode='r') as zf:
            output_string = zf.read(zf.namelist()[0]).decode("UTF-8")
            actual_output = json.loads(output_string)
            assert expected_output == actual_output
