import os
import logging
import json
import boto3
from shopify_inventory_mapping.dynamodb import insert_item

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)

SQS = boto3.resource("sqs", os.environ['REGION'])
QUEUE = SQS.get_queue_by_name(QueueName=os.environ['MAPPING_QUEUE_NAME']) # pylint: disable=no-member
TENANT = os.environ.get('TENANT', 'frankandoak')
STAGE = os.environ.get('STAGE', 'x')


def handler(_, context): # pylint: disable=unused-argument
    messages = QUEUE.receive_messages(
        MaxNumberOfMessages=10,
        WaitTimeSeconds=20
    )

    for message in messages:
        try:
            products = json.loads(message.body)
            LOGGER.info(f'Processing Message')

            import_to_dynamodb(products)

            LOGGER.info('Deleting message from queue...')
            message.delete()

        except Exception as e: # pylint: disable=broad-except
            LOGGER.exception(e)


    return {
        "success": True
    }

def import_to_dynamodb(products):
    if products['items']:
        LOGGER.info(f'Adding product mapping to the table')
        for variant in products['items']:
            insert_item(os.environ['dynamo_mapping_table_name'], variant)
