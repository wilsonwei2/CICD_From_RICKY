import os
import logging
import json
import boto3
from boto3.dynamodb.conditions import Key
from historical_orders_returns.lambdas.order_transformer import OrderTransformer
from historical_orders_returns.lambdas.return_transformer import ReturnTransformer
from newstore_common.aws import init_root_logger

init_root_logger(__name__)
LOGGER = logging.getLogger(__name__)

ORDERS_TABLE_NAME = os.environ['ORDERS_TABLE_NAME']
RETURNS_TABLE_NAME = os.environ['RETURNS_TABLE_NAME']
DYNAMODB = boto3.resource('dynamodb', region_name='us-east-1')
ORDERS_TABLE = DYNAMODB.Table(ORDERS_TABLE_NAME)
RETURNS_TABLE = DYNAMODB.Table(RETURNS_TABLE_NAME)

SQS = boto3.resource("sqs", os.environ['REGION'])
ORDERS_QUEUE_NAME = os.environ['ORDERS_QUEUE_NAME']
ORDERS_QUEUE = SQS.get_queue_by_name(QueueName=ORDERS_QUEUE_NAME)
RETURNS_QUEUE_NAME = os.environ['RETURNS_QUEUE_NAME']
RETURNS_QUEUE = SQS.get_queue_by_name(QueueName=RETURNS_QUEUE_NAME)


# get order entries from dynamodb where status = new
def get_dynamodb_orders():
    LOGGER.info("Getting orders from DynamoDB...")

    results = []
    last_evaluated_key = None

    while True:
        if last_evaluated_key:
            response = ORDERS_TABLE.scan(
                FilterExpression=Key('status').eq('new'),
                ExclusiveStartKey=last_evaluated_key
            )
        else:
            response = ORDERS_TABLE.scan(FilterExpression=Key('status').eq('new'))

        last_evaluated_key = response.get('LastEvaluatedKey')

        results.extend(response['Items'])

        if not last_evaluated_key or len(results) > 500:
            break

    return results


# get return entries from dynamodb where status = new
def get_dynamodb_returns():
    LOGGER.info("Getting returns from DynamoDB...")
    res = RETURNS_TABLE.scan(FilterExpression=Key('status').eq('new'))
    if not res or "Items" not in res:
        LOGGER.error(f"Failed to query returns in DynamoDB table.")
        return []
    return res["Items"]

# update order status in dynamodb
def update_dynamodb_order_status(order_id, update_status):
    LOGGER.info(f"Updating order {order_id} in DynamoDB with status {update_status}")

    res = ORDERS_TABLE.update_item(
        Key={'order_id': order_id},
        UpdateExpression='SET #update_status = :update_status',
        ExpressionAttributeValues={':update_status': update_status},
        ExpressionAttributeNames={"#update_status": "status"}
    )

    if not res:
        LOGGER.error(f"Failed to update order {order_id} in DynamoDB table.")


# update order status in dynamodb
def update_dynamodb_return_status(rma_id, update_status):
    LOGGER.info(f"Updating return {rma_id} in DynamoDB with status {update_status}")

    res = RETURNS_TABLE.update_item(
        Key={'rma_id': rma_id},
        UpdateExpression='SET #update_status = :update_status',
        ExpressionAttributeValues={':update_status': update_status},
        ExpressionAttributeNames={"#update_status": "status"}
    )

    if not res:
        LOGGER.error(f"Failed to update return {rma_id} in DynamoDB table.")


# sending order to queue
def send_order_to_sqs(ns_order):
    LOGGER.info(f"Sending order {ns_order['external_id']} to queue...")

    payload = json.dumps(ns_order)
    return ORDERS_QUEUE.send_message(MessageBody=payload, MessageGroupId=ORDERS_QUEUE.url, MessageDeduplicationId=str(hash(payload)))


# sending return to queue
def send_return_to_sqs(ns_return):
    # LOGGER.info(f"Sending return {ns_return['external_id']} to queue...")

    payload = json.dumps(ns_return)
    return RETURNS_QUEUE.send_message(MessageBody=payload, MessageGroupId=RETURNS_QUEUE.url, MessageDeduplicationId=str(hash(payload)))


def handler_orders(*_):
    order_transformer = OrderTransformer()
    order_table_entries = get_dynamodb_orders()

    for order_table_entry in order_table_entries:
        order = json.loads(order_table_entry["payload"])
        update_status = "extraction_failed"

        try:
            ns_order = order_transformer.transform_order(order=order)
            sqs_res = send_order_to_sqs(ns_order)
            if (sqs_res and "MessageId" in sqs_res):
                update_status = "extracted"
        except Exception as e: # pylint: disable=broad-except
            LOGGER.error(f"Failed to transform order {order_table_entry['order_id']}")
            LOGGER.error(e)

        update_dynamodb_order_status(order_table_entry["order_id"], update_status)

    return {
        "success": True
    }

def handler_returns(event, context): # pylint: disable=unused-argument
    return_transformer = ReturnTransformer(context)
    return_table_entries = get_dynamodb_returns()

    for return_table_entry in return_table_entries:
        return_entry = json.loads(return_table_entry["payload"])
        update_status = "extraction_failed"

        try:
            ns_return = return_transformer.transform_return(return_entry)
            sqs_res = send_return_to_sqs(ns_return)
            if (sqs_res and "MessageId" in sqs_res):
                update_status = "extracted"
        except Exception as e: # pylint: disable=broad-except
            LOGGER.error(f"Failed to transform return {return_table_entry['rma_id']}")
            LOGGER.error(e)

        update_dynamodb_return_status(return_table_entry["rma_id"], update_status)
    return {
        "success": True
    }
