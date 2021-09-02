import json
import boto3
from moto import mock_sqs, mock_ssm


def mock_fulfill_order(*_, **__):
    return {}

@mock_ssm
@mock_sqs
def test_sqs_to_newstore(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("QUEUE_NAME", "testqueue.fifo")
    monkeypatch.setenv("TYPE", "order")

    from newstore_adapter.connector import NewStoreConnector
    monkeypatch.setattr(NewStoreConnector, "fulfill_order", mock_fulfill_order)

    # create queue
    sqs = boto3.client("sqs", "us-east-1")
    queue = sqs.create_queue(QueueName="testqueue.fifo", Attributes={"FifoQueue": "true"})

    # create queue entry
    input_file = open("data/input/order_queue_entry.json", "r")
    payload = input_file.read()
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload)))
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload) + 1))
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload) + 2))
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload) + 3))
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload) + 4))
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload) + 5))
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload) + 6))
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload) + 7))
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload) + 8))
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload) + 9))
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload) + 10))
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload) + 11))
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload) + 12))
    sqs.send_message(QueueUrl=queue['QueueUrl'], MessageBody=payload, MessageGroupId=queue['QueueUrl'], MessageDeduplicationId=str(hash(payload) + 13))

    # prepare ssm
    ssm = boto3.client('ssm', "us-east-1")
    ssm.put_parameter(
        Name="/frankandoak/x/newstore",
        Value=json.dumps({'username': 'mock', 'password': 'mock', 'host': 'mock'}),
        Type="String"
    )

    from historical_orders_returns.lambdas.sqs_to_newstore import handler
    result = handler(None, None)

    # assert successful function execution
    assert result["success"]

    # assert message in queue
    sqs_res = boto3.resource("sqs", "us-east-1")
    queue = sqs_res.get_queue_by_name(QueueName="testqueue.fifo")
    messages = queue.receive_messages(
        MaxNumberOfMessages=10,
        WaitTimeSeconds=0
    )
    assert len(messages) == 0
