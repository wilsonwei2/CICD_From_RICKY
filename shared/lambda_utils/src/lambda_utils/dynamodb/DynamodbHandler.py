import logging
import os
import json
import boto3
import datetime

logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)


class DynamodbHandler:


    def __init__(self):

        self.bucket = ''
        self.bucket_name = ''
        self.bucket_key = ''
        self.dynamo_table = os.environ['dynamo_table_name']

        logger.info("create instance of DynamoHandler")


    """
    Insert in the dynamodb the id range processed 
    """
    def insert_item(self, item):

        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(self.dynamo_table)

        table.put_item(
            Item=item
        )


    """
    Insert in the dynamodb the id range processed 
    """
    def insert(self, ids):
        logger.info("dynamo - insert - ids")
        logger.info(ids)
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(self.dynamo_table)
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d %H:%M:%S")
        end_id = len(ids)
        start_id = ids[0]

        id  = 10


        table.put_item(
            Item={
                'last_runtime': date,
                'last_id_netsuite_processed': end_id,
                'last_date_processed': date,
                'id': self.id
            }
        )


    def read(self, id):
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(self.dynamo_table)
        try:
            response = table.get_item(
                Key={
                    'id': id
                }
            )
        except Exception as e:
            raise Exception(e)
            print(e.response['Error']['Message'])

        return response


    def update_current_id(self, current_id):
        end_id = int(os.environ['netsuite_end_id'])

        if current_id == end_id:
            current_id = 0

        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(self.dynamo_table)
        id = 10
        response = table.update_item(
            Key={
                'id': id
            },
            UpdateExpression="set current_id = :c_id",
            ExpressionAttributeValues={
                ':c_id': current_id
            },
            ReturnValues="UPDATED_NEW"
        )

    def update_shipping_status(self, id, last_date_processed, last_tran_id):

        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d %H:%M:%S")

        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(self.dynamo_table)

        response = table.update_item(
            Key={
                'id': id
            },
            UpdateExpression="set last_date_processed = :last_date_processed, last_runtime = :last_runtime, last_id_netsuite_processed = :last_id_netsuite_processed",
            ExpressionAttributeValues={
                ':last_date_processed': last_date_processed,
                ':last_runtime': date,
                ':last_id_netsuite_processed': last_tran_id
            },
            ReturnValues="UPDATED_NEW"
        )
