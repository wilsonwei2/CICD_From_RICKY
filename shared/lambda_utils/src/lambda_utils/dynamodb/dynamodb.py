import json
import decimal
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)

class DynamoDB(object):
    def __init__(self):
        self.dynamodb_client = boto3.client('dynamodb')
        self.dynamodb_resource = boto3.resource('dynamodb')

    def list_existing_tables(self):
        return self.dynamodb_client.list_tables()['TableNames']

    def create_table(self, schema):
        existing_tables = self.list_existing_tables()
        table_name = schema['TableName']
        # Create table only if it doesn't exists
        if table_name not in existing_tables:
            response = self.dynamodb_resource.create_table(
                TableName=schema['TableName'],
                KeySchema=schema['KeySchema'],
                AttributeDefinitions=schema['AttributeDefinitions'],
                ProvisionedThroughput=schema['ProvisionedThroughput']
            )
            logger.info("Table status: %s" % str(response.table_status))

    def insert_item(self, table_name, item):
        logger.info('Insert item in table %s' % table_name)
        logger.debug(json.dumps(item, indent=4))
        
        table = self.dynamodb_resource.Table(table_name)
        response = table.put_item(
            Item=_marshal_dyn_obj(item)
        )

        logger.info("PutItem succeeded:")
        logger.info(json.dumps(response, indent=4, cls=DecimalEncoder))

    def get_item(self, table_name, key):
        logger.info('Get item in table %s' % table_name)
        logger.info(json.dumps(key, indent=4))
        
        table = self.dynamodb_resource.Table(table_name)

        try:
            response = table.get_item(
                Key=key
            )
        except ClientError as e:
            logger.error(e.response['Error']['Message'])
            return None
        else:
            logger.info("GetItem succeeded:")
            logger.info(json.dumps(response, indent=4, cls=DecimalEncoder))
            return response.get('Item')

    def update_item(self, table_name, key, update_expression, expression_attribute_values, return_values="UPDATED_NEW"):
        logger.info('Update item in table %s' % table_name)
        logger.debug(json.dumps(key, indent=4))
        
        table = self.dynamodb_resource.Table(table_name)
        response = table.update_item(
            Key=key,
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues=return_values
        )

        logger.info("UpdateItem succeeded: %s" % (json.dumps(response, indent=4, cls=DecimalEncoder)))
        
def _marshal_dyn_obj(o):    
    '''Return shallow copy of dict with empty strings replaced with None and float with Decimal'''  
    ret = {}
    for k,v in o.items():   
        if isinstance(v, dict): 
            ret[k] = _marshal_dyn_obj(v)    
        elif isinstance(v, list):   
            ret[k] = [_marshal_dyn_obj(i) if isinstance(i, dict) else i for i in v] 
        elif isinstance(v, float):  
            ret[k] = decimal.Decimal(str(v))    
        elif v == '':   
            ret[k] = None   
        else:   
            ret[k] = v  
    return ret

class DecimalEncoder(json.JSONEncoder):
    '''Helper class to convert a DynamoDB item to JSON.'''
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if abs(o) % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)
