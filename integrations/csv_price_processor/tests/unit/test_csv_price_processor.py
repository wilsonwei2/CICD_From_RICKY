import boto3
from moto import mock_s3

REGION = 'us-east-1'
TEST_BUCKET_NAME = 'testbucket'
TEST_OBJECT_KEY = 'path/to/FAONSPRC_CAD_RET_20210428123211.csv'
TEST_OBJECT2_KEY = 'path/to/FAONSPRC_CAD_SAL_20210428123211.csv'


@mock_s3
def test_find_records(monkeypatch):
    monkeypatch.setenv('S3_BUCKET', TEST_BUCKET_NAME)
    monkeypatch.setenv('S3_PREFIX', 'foo')
    monkeypatch.setenv('CHUNK_SIZE', '10')
    monkeypatch.setenv('SECS_BETWEEN_CHUNKS', '300')
    monkeypatch.setenv('STATE_MACHINE_ARN', 'bar')
    monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
    monkeypatch.setenv('SOURCE_PREFIX', 'path/to/FAONSPRC_')

    s3r = boto3.resource('s3', region_name=REGION)
    bucket = s3r.create_bucket(Bucket=TEST_BUCKET_NAME) # pylint: disable=no-member

    import_obj = s3r.Object(TEST_BUCKET_NAME, TEST_OBJECT_KEY) # pylint: disable=no-member
    import_obj.put(Body='test')

    from csv_price_processor.aws.csv_price_processor import find_records

    result = find_records()
    assert len(result) == 0

    import_obj = s3r.Object(TEST_BUCKET_NAME, TEST_OBJECT2_KEY) # pylint: disable=no-member
    import_obj.put(Body='test')

    result = find_records()
    assert len(result) == 2
    assert result[0]['object_key'] == TEST_OBJECT_KEY
    assert result[1]['object_key'] == TEST_OBJECT2_KEY
