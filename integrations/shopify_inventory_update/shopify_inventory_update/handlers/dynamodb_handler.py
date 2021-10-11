import json
import decimal
import logging
import os
import boto3 # pylint: disable=import-error
from botocore.exceptions import ClientError

LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
logger = logging.getLogger(__file__)
logger.setLevel(LOG_LEVEL)


def get_dynamodb_client():
    return boto3.client('dynamodb')


def get_dynamodb_resource():
    return boto3.resource('dynamodb')


def list_existing_tables(dynamodb_client=None):
    if not dynamodb_client:
        dynamodb_client=get_dynamodb_client()
    return dynamodb_client.list_tables()['TableNames']


def create_table(schema, dynamodb=None):
    if not dynamodb:
        dynamodb = get_dynamodb_resource()
    existing_tables = list_existing_tables()
    table_name = schema['TableName']
    # Create table only if it doesn't exists
    if table_name not in existing_tables:
        response = dynamodb.create_table(
            TableName=schema['TableName'],
            KeySchema=schema['KeySchema'],
            AttributeDefinitions=schema['AttributeDefinitions'],
            ProvisionedThroughput=schema['ProvisionedThroughput']
        )
        logger.info("Table status: %s" % str(response.table_status))


def insert_item(table_name, item, dynamodb=None):
    if not dynamodb:
        dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    response = table.put_item(
        Item=item
    )
    logger.info("PutItem succeeded:")
    logger.info(json.dumps(response, indent=4, cls=DecimalEncoder))


def get_item(table_name, item, dynamodb=None, consistent_read=False):
    if not dynamodb:
        dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    try:
        response = table.get_item(
            Key=item,
            ConsistentRead=consistent_read,
        )
    except ClientError as e:
        logger.exception(str(e.response['Error']['Message']))
    else:
        if response.get('Item'):
            response_item = response['Item']
            logger.info("GetItem succeeded:")
            logger.info(json.dumps(response_item, indent=4, cls=DecimalEncoder))
            return response_item
        else:
            logger.info("Item doesn't exist.")
            return None


def get_all(table_name, dynamodb=None):
    if not dynamodb:
        dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    try:
        response = table.scan()
        items = response.get('Items', [])
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items = items + response.get('Items', [])
    except ClientError as e:
        logger.exception(str(e.response['Error']['Message']))

    return items


def update_item(table_name, schema, dynamodb=None):
    if not dynamodb:
        dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    response = table.update_item(
        Key=schema['Key'],
        UpdateExpression=schema['UpdateExpression'],
        ExpressionAttributeValues=schema['ExpressionAttributeValues']
    )
    logger.info("UpdateItem succeeded:")
    logger.info(json.dumps(response, indent=4, cls=DecimalEncoder))


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if abs(o) % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)
