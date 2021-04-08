import os
from lambda_utils.dynamodb.dynamodb import DynamoDB
from lambda_utils.emailer import reports
from datetime import datetime

class ReportError(object):
    # params is os.environ
    def __init__(self, params, table_name):
        self.params = params
        self.table_name =  table_name
        self.dynamodb = DynamoDB()

    def report(self, order_id, msg, subject):
        if not self.was_reported(order_id, msg):
            if reports.send(self.params, subject=subject, body=msg):
                self.insert_report_on_dynamo(order_id, msg)
        else:
            self.update_report_on_dynamo(order_id, msg)

    def was_reported(self, order_id, msg):
        self.check_and_create_table()
        key = {
            'order_external_id': order_id,
            'error_message': msg
        }
        item_report = self.dynamodb.get_item(self.table_name, key)
        return bool(item_report)

    def check_and_create_table(self):
        schema = {
            'TableName': self.table_name,
            'KeySchema': [
                {
                    'AttributeName': 'order_external_id',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'error_message',
                    'KeyType': 'RANGE'
                }
            ],
            'AttributeDefinitions': [
                {
                    'AttributeName': 'order_external_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'error_message',
                    'AttributeType': 'S'
                }
            ],
            'ProvisionedThroughput': {
                'ReadCapacityUnits': 10,
                'WriteCapacityUnits': 10
            }
        }
        self.dynamodb.create_table(schema)

    def insert_report_on_dynamo(self, order_id, msg):
        item = {
            'order_external_id': order_id,
            'error_message': msg,
            'datetime': datetime.utcnow().isoformat(),
            'error_count': 1
        }
        self.dynamodb.insert_item(self.table_name, item)

    def update_report_on_dynamo(self, order_id, msg):
        key = {
            'order_external_id': order_id,
            'error_message': msg
        }
        update_expression = "set last_datetime = :l_d, error_count = error_count + :val"
        expression_attribute_values = {
            ':l_d': datetime.utcnow().isoformat(),
            ':val': 1
        }
        self.dynamodb.update_item(
            self.table_name, 
            key, 
            update_expression, 
            expression_attribute_values
        )
