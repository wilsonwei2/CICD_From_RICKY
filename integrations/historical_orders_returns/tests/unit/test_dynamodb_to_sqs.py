import json
import boto3
from moto import mock_sqs, mock_dynamodb2
from newstore_adapter.connector import NewStoreConnector


@mock_sqs
@mock_dynamodb2
def test_order_dynamodb_to_sqs(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("ORDERS_QUEUE_NAME", "testqueue.fifo")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_QUEUE_NAME", "testqueue.fifo")

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'}
        ])

    # create table entry
    input_file = open("data/input/order_table_entry.json", "r")
    item = json.load(input_file)
    table.put_item(Item=item)

    # create queue
    sqs = boto3.client("sqs", "us-east-1")
    queue = sqs.create_queue(QueueName="testqueue.fifo", Attributes={"FifoQueue": "true"})

    from historical_orders_returns.lambdas.dynamodb_to_sqs import handler_orders
    result = handler_orders(None, None)

    # assert successful function execution
    assert result["success"]

    # assert dynamodb update status
    res = table.scan()
    assert len(res["Items"]) == 1
    assert res["Items"][0]["status"] == "extracted"

    # assert message in queue
    response = sqs.receive_message(QueueUrl=queue["QueueUrl"])
    assert len(response["Messages"]) == 1

    output_file = open("data/input/order_queue_entry.json", "r")
    ns_order = json.load(output_file)

    assert json.loads(response["Messages"][0]["Body"]) == ns_order


@mock_sqs
@mock_dynamodb2
def test_order_dynamodb_to_sqs_order_discount(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("ORDERS_QUEUE_NAME", "testqueue.fifo")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_QUEUE_NAME", "testqueue.fifo")

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'}
        ])

    # create table entry
    input_file = open("data/input/order_table_entry_discount.json", "r")
    item = json.load(input_file)
    table.put_item(Item=item)

    # create queue
    sqs = boto3.client("sqs", "us-east-1")
    queue = sqs.create_queue(QueueName="testqueue.fifo", Attributes={"FifoQueue": "true"})

    from historical_orders_returns.lambdas.dynamodb_to_sqs import handler_orders
    result = handler_orders(None, None)

    # assert successful function execution
    assert result["success"]

    # assert dynamodb update status
    res = table.scan()
    assert len(res["Items"]) == 1
    assert res["Items"][0]["status"] == "extracted"

    # assert message in queue
    response = sqs.receive_message(QueueUrl=queue["QueueUrl"])
    assert len(response["Messages"]) == 1

    output_file = open("data/input/order_queue_entry_discount.json", "r")
    ns_order = json.load(output_file)

    assert json.loads(response["Messages"][0]["Body"]) == ns_order

@mock_sqs
@mock_dynamodb2
def test_order_dynamodb_to_sqs_order_single_discount(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("ORDERS_QUEUE_NAME", "testqueue.fifo")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_QUEUE_NAME", "testqueue.fifo")

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'}
        ])

    # create table entry
    input_file = open("data/input/order_table_entry_single_discount.json", "r")
    item = json.load(input_file)
    table.put_item(Item=item)

    # create queue
    sqs = boto3.client("sqs", "us-east-1")
    queue = sqs.create_queue(QueueName="testqueue.fifo", Attributes={"FifoQueue": "true"})

    from historical_orders_returns.lambdas.dynamodb_to_sqs import handler_orders
    result = handler_orders(None, None)

    # assert successful function execution
    assert result["success"]

    # assert dynamodb update status
    res = table.scan()
    assert len(res["Items"]) == 1
    assert res["Items"][0]["status"] == "extracted"

    # assert message in queue
    response = sqs.receive_message(QueueUrl=queue["QueueUrl"])
    assert len(response["Messages"]) == 1

    output_file = open("data/input/order_queue_entry_single_discount.json", "r")
    ns_order = json.load(output_file)

    assert json.loads(response["Messages"][0]["Body"]) == ns_order


@mock_sqs
@mock_dynamodb2
def test_order_dynamodb_to_sqs_order_percentage_discount(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("ORDERS_QUEUE_NAME", "testqueue.fifo")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_QUEUE_NAME", "testqueue.fifo")

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'}
        ])

    # create table entry
    input_file = open("data/input/order_table_entry_percentage_discount.json", "r")
    item = json.load(input_file)
    table.put_item(Item=item)

    # create queue
    sqs = boto3.client("sqs", "us-east-1")
    queue = sqs.create_queue(QueueName="testqueue.fifo", Attributes={"FifoQueue": "true"})

    from historical_orders_returns.lambdas.dynamodb_to_sqs import handler_orders
    result = handler_orders(None, None)

    # assert successful function execution
    assert result["success"]

    # assert dynamodb update status
    res = table.scan()
    assert len(res["Items"]) == 1
    assert res["Items"][0]["status"] == "extracted"

    # assert message in queue
    response = sqs.receive_message(QueueUrl=queue["QueueUrl"])
    assert len(response["Messages"]) == 1

    output_file = open("data/input/order_queue_entry_percentage_discount.json", "r")
    ns_order = json.load(output_file)

    assert json.loads(response["Messages"][0]["Body"]) == ns_order


@mock_sqs
@mock_dynamodb2
def test_return_dynamodb_to_sqs(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("ORDERS_QUEUE_NAME", "testqueue.fifo")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_QUEUE_NAME", "testqueue.fifo")

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'rma_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'rma_id', 'AttributeType': 'S'}
        ])

    # create table entry
    input_file = open("data/input/return_table_entry.json", "r")
    item = json.load(input_file)
    table.put_item(Item=item)

    # create queue
    sqs = boto3.client("sqs", "us-east-1")
    queue = sqs.create_queue(QueueName="testqueue.fifo", Attributes={"FifoQueue": "true"})

    monkeypatch.setattr(NewStoreConnector, "graphql", lambda *_, **__: {
        "orders": {
            "edges": [
                {
                    "node": {
                        "id": "0e7e736b-333e-4715-abc6-318bc1b6c6cb"
                    }
                }
            ]
        }
    })

    from historical_orders_returns.lambdas.dynamodb_to_sqs import handler_returns
    result = handler_returns(None, None)

    # assert successful function execution
    assert result["success"]

    # assert dynamodb update status
    res = table.scan()
    assert len(res["Items"]) == 1
    assert res["Items"][0]["status"] == "extracted"

    # assert message in queue
    response = sqs.receive_message(QueueUrl=queue["QueueUrl"])
    assert len(response["Messages"]) == 1

    output_file = open("data/input/return_queue_entry.json", "r")
    ns_order = json.load(output_file)
    assert json.loads(response["Messages"][0]["Body"]) == ns_order


@mock_sqs
@mock_dynamodb2
def test_order_dynamodb_to_sqs_discount_no_amount(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("ORDERS_QUEUE_NAME", "testqueue.fifo")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_QUEUE_NAME", "testqueue.fifo")

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'}
        ])

    # create table entry
    input_file = open("data/input/order_table_entry_discount_no_amount.json", "r")
    item = json.load(input_file)
    table.put_item(Item=item)

    # create queue
    sqs = boto3.client("sqs", "us-east-1")
    queue = sqs.create_queue(QueueName="testqueue.fifo", Attributes={"FifoQueue": "true"})

    from historical_orders_returns.lambdas.dynamodb_to_sqs import handler_orders
    result = handler_orders(None, None)

    # assert successful function execution
    assert result["success"]

    # assert dynamodb update status
    res = table.scan()
    assert len(res["Items"]) == 1
    assert res["Items"][0]["status"] == "extracted"

    # assert message in queue
    response = sqs.receive_message(QueueUrl=queue["QueueUrl"])
    assert len(response["Messages"]) == 1

    output_file = open("data/input/order_queue_entry_discount_no_amount.json", "r")
    ns_order = json.load(output_file)

    assert json.loads(response["Messages"][0]["Body"]) == ns_order


@mock_sqs
@mock_dynamodb2
def test_order_dynamodb_to_sqs_tax_cent_adjustment(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("ORDERS_QUEUE_NAME", "testqueue.fifo")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_QUEUE_NAME", "testqueue.fifo")

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'}
        ])

    # create table entry
    input_file = open("data/input/order_table_entry_tax_issue.json", "r")
    item = json.load(input_file)
    table.put_item(Item=item)

    # create queue
    sqs = boto3.client("sqs", "us-east-1")
    queue = sqs.create_queue(QueueName="testqueue.fifo", Attributes={"FifoQueue": "true"})

    from historical_orders_returns.lambdas.dynamodb_to_sqs import handler_orders
    result = handler_orders(None, None)

    # assert successful function execution
    assert result["success"]

    # assert dynamodb update status
    res = table.scan()
    assert len(res["Items"]) == 1
    assert res["Items"][0]["status"] == "extracted"

    # assert message in queue
    response = sqs.receive_message(QueueUrl=queue["QueueUrl"])
    assert len(response["Messages"]) == 1

    output_file = open("data/input/order_queue_entry_tax_issue.json", "r")
    ns_order = json.load(output_file)

    assert json.loads(response["Messages"][0]["Body"]) == ns_order


@mock_sqs
@mock_dynamodb2
def test_order_dynamodb_to_sqs_tax_cent_adjustment_2(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("ORDERS_QUEUE_NAME", "testqueue.fifo")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_QUEUE_NAME", "testqueue.fifo")

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'}
        ])

    # create table entry
    input_file = open("data/input/order_table_entry_tax_issue-2.json", "r")
    item = json.load(input_file)
    table.put_item(Item=item)

    # create queue
    sqs = boto3.client("sqs", "us-east-1")
    queue = sqs.create_queue(QueueName="testqueue.fifo", Attributes={"FifoQueue": "true"})

    from historical_orders_returns.lambdas.dynamodb_to_sqs import handler_orders
    result = handler_orders(None, None)

    # assert successful function execution
    assert result["success"]

    # assert dynamodb update status
    res = table.scan()
    assert len(res["Items"]) == 1
    assert res["Items"][0]["status"] == "extracted"

    # assert message in queue
    response = sqs.receive_message(QueueUrl=queue["QueueUrl"])
    assert len(response["Messages"]) == 1

    output_file = open("data/input/order_queue_entry_tax_issue-2.json", "r")
    ns_order = json.load(output_file)

    assert json.loads(response["Messages"][0]["Body"]) == ns_order

@mock_sqs
@mock_dynamodb2
def test_order_dynamodb_to_sqs_tax_cent_adjustment_3(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("ORDERS_QUEUE_NAME", "testqueue.fifo")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_QUEUE_NAME", "testqueue.fifo")

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'}
        ])

    # create table entry
    input_file = open("data/input/order_table_entry_tax_issue-3.json", "r")
    item = json.load(input_file)
    table.put_item(Item=item)

    # create queue
    sqs = boto3.client("sqs", "us-east-1")
    queue = sqs.create_queue(QueueName="testqueue.fifo", Attributes={"FifoQueue": "true"})

    from historical_orders_returns.lambdas.dynamodb_to_sqs import handler_orders
    result = handler_orders(None, None)

    # assert successful function execution
    assert result["success"]

    # assert dynamodb update status
    res = table.scan()
    assert len(res["Items"]) == 1
    assert res["Items"][0]["status"] == "extracted"

    # assert message in queue
    response = sqs.receive_message(QueueUrl=queue["QueueUrl"])
    assert len(response["Messages"]) == 1

    output_file = open("data/input/order_queue_entry_tax_issue-3.json", "r")
    ns_order = json.load(output_file)

    assert json.loads(response["Messages"][0]["Body"]) == ns_order


@mock_sqs
@mock_dynamodb2
def test_order_dynamodb_to_sqs_tax_cent_adjustment_4(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("ORDERS_QUEUE_NAME", "testqueue.fifo")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_QUEUE_NAME", "testqueue.fifo")

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'}
        ])

    # create table entry
    input_file = open("data/input/order_table_entry_tax_issue-4.json", "r")
    item = json.load(input_file)
    table.put_item(Item=item)

    # create queue
    sqs = boto3.client("sqs", "us-east-1")
    queue = sqs.create_queue(QueueName="testqueue.fifo", Attributes={"FifoQueue": "true"})

    from historical_orders_returns.lambdas.dynamodb_to_sqs import handler_orders
    result = handler_orders(None, None)

    # assert successful function execution
    assert result["success"]

    # assert dynamodb update status
    res = table.scan()
    assert len(res["Items"]) == 1
    assert res["Items"][0]["status"] == "extracted"

    # assert message in queue
    response = sqs.receive_message(QueueUrl=queue["QueueUrl"])
    assert len(response["Messages"]) == 1

    output_file = open("data/input/order_queue_entry_tax_issue-4.json", "r")
    ns_order = json.load(output_file)

    assert json.loads(response["Messages"][0]["Body"]) == ns_order


@mock_sqs
@mock_dynamodb2
def test_order_dynamodb_to_sqs_gc_payment(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("ORDERS_QUEUE_NAME", "testqueue.fifo")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_QUEUE_NAME", "testqueue.fifo")

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'}
        ])

    # create table entry
    input_file = open("data/input/order_table_entry_gc_payment.json", "r")
    item = json.load(input_file)
    table.put_item(Item=item)

    # create queue
    sqs = boto3.client("sqs", "us-east-1")
    queue = sqs.create_queue(QueueName="testqueue.fifo", Attributes={"FifoQueue": "true"})

    from historical_orders_returns.lambdas.dynamodb_to_sqs import handler_orders
    result = handler_orders(None, None)

    # assert successful function execution
    assert result["success"]

    # assert dynamodb update status
    res = table.scan()
    assert len(res["Items"]) == 1
    assert res["Items"][0]["status"] == "extracted"

    # assert message in queue
    response = sqs.receive_message(QueueUrl=queue["QueueUrl"])
    assert len(response["Messages"]) == 1

    output_file = open("data/input/order_queue_entry_gc_payment.json", "r")
    ns_order = json.load(output_file)

    assert json.loads(response["Messages"][0]["Body"]) == ns_order


@mock_sqs
@mock_dynamodb2
def test_order_dynamodb_to_sqs_mixed_payment(monkeypatch):
    # mock environment & functions
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("REGION", "us-east-1")
    monkeypatch.setenv("TENANT", "frankandoak")
    monkeypatch.setenv("STAGE", "x")
    monkeypatch.setenv("ORDERS_TABLE_NAME", "testtable")
    monkeypatch.setenv("ORDERS_QUEUE_NAME", "testqueue.fifo")
    monkeypatch.setenv("RETURNS_TABLE_NAME", "testtable")
    monkeypatch.setenv("RETURNS_QUEUE_NAME", "testqueue.fifo")

    # create dynamodb
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName="testtable",
        KeySchema=[
            {'AttributeName': 'order_id', 'KeyType': 'HASH'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'order_id', 'AttributeType': 'S'}
        ])

    # create table entry
    input_file = open("data/input/order_table_entry_mixed_payment.json", "r")
    item = json.load(input_file)
    table.put_item(Item=item)

    # create queue
    sqs = boto3.client("sqs", "us-east-1")
    queue = sqs.create_queue(QueueName="testqueue.fifo", Attributes={"FifoQueue": "true"})

    from historical_orders_returns.lambdas.dynamodb_to_sqs import handler_orders
    result = handler_orders(None, None)

    # assert successful function execution
    assert result["success"]

    # assert dynamodb update status
    res = table.scan()
    assert len(res["Items"]) == 1
    assert res["Items"][0]["status"] == "extracted"

    # assert message in queue
    response = sqs.receive_message(QueueUrl=queue["QueueUrl"])
    assert len(response["Messages"]) == 1

    output_file = open("data/input/order_queue_entry_mixed_payment.json", "r")
    ns_order = json.load(output_file)

    assert json.loads(response["Messages"][0]["Body"]) == ns_order
