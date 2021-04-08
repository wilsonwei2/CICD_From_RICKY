import json
import decimal
import os
import logging
import boto3
from botocore.exceptions import ClientError

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)

NETSUITE_VALIDATION_TABLE = str(os.environ.get('NETSUITE_VALIDATION_TABLE', 'shopify_netsuite_id_import_validation'))


def get_dynamodb_client():
    return boto3.client('dynamodb')


def get_dynamodb_resource():
    return boto3.resource('dynamodb')


def list_existing_tables(dynamodb_client=None):
    if not dynamodb_client:
        dynamodb_client = get_dynamodb_client()
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
        LOGGER.info(f"Table status: {str(response.table_status)}")


def insert_item(table_name, item, dynamodb=None):
    if not dynamodb:
        dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    response = table.put_item(
        Item=item
    )
    LOGGER.debug(json.dumps(response, indent=4, cls=DecimalEncoder))


def insert_product_variant_data(dynamodb=None, variant_id=str, ns_id=str, p_id=str, inv_item_id=str):
    if not dynamodb:
        dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(NETSUITE_VALIDATION_TABLE)
    response = {}
    key = {
        'variant_id':variant_id
    }
    update_expression = "set netsuite_id=:ns_id, product_id=:p_id, inventory_item_id=:inv_item_id"
    expression_attribute_values = {
        ':ns_id': str(ns_id),
        ':p_id': str(p_id),
        ':inv_item_id': str(inv_item_id)
    }

    try:
        response = table.update_item(
            Key=key,
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values
        )
    except ClientError as e:
        LOGGER.info('Error inserting into Shopify Netsuite Table')
        LOGGER.exception(str(e.response['Error']['Message']))
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
