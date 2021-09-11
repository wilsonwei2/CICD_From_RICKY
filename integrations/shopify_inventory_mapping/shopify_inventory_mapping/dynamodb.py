import json
import decimal
import logging
import boto3
from botocore.exceptions import ClientError

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)


def get_dynamodb_client():
    return boto3.client('dynamodb')


def get_dynamodb_resource():
    return boto3.resource('dynamodb')


def insert_item(table_name, item, dynamodb=None):
    if not dynamodb:
        dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    response = table.put_item(
        Item=item
    )
    LOGGER.debug(json.dumps(response, indent=4, cls=DecimalEncoder))


def get_item(table_name, item, dynamodb=None):
    if not dynamodb:
        dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    try:
        response = table.get_item(
            Key=item
        )
    except ClientError as e:
        LOGGER.exception(str(e.response['Error']['Message']))
    else:
        if response.get('Item'):
            response_item = response['Item']
            return response_item

        LOGGER.info("Item doesn't exist.")
        return None


def update_item(table_name, schema, dynamodb=None):
    if not dynamodb:
        dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    response = table.update_item(
        Key=schema['Key'],
        UpdateExpression=schema['UpdateExpression'],
        ExpressionAttributeValues=schema['ExpressionAttributeValues'],
        ReturnValues=schema['ReturnValues']
    )
    LOGGER.debug(json.dumps(response, indent=4, cls=DecimalEncoder))


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o): # pylint: disable=E0202
        if isinstance(o, decimal.Decimal):
            if abs(o) % 1 > 0:
                return float(o)
            return int(o)
        return super(DecimalEncoder, self).default(o)
