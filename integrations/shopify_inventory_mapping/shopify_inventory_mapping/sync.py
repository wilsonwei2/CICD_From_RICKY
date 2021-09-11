import boto3
from lambda_utils.events.events_handler import EventsHandler
from shopify_inventory_mapping.transformers.transform import process_transformation
from shopify_inventory_mapping.dynamodb import get_dynamodb_resource, get_item, update_item
from shopify_inventory_mapping.shopify.graphql import ShopifyAPI
import logging
import os
import json

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)

TRIGGER_NAME = str(os.environ.get('trigger_name', 'shopify_import_inventory_mapping_trigger'))

TENANT = os.environ.get('TENANT') or 'frankandoak'
STAGE = os.environ.get('STAGE') or 'x'
REGION = os.environ.get('REGION') or 'us-east-1'

SQS = boto3.resource("sqs", os.environ['REGION'])
MAPPING_QUEUE = SQS.get_queue_by_name(QueueName=os.environ['MAPPING_QUEUE_NAME']) # pylint: disable=no-member

def run():
    dynamodb = get_dynamodb_resource()
    events_handler = EventsHandler()
    shopify_api = ShopifyAPI()

    try:
        item = get_item(os.environ['dynamo_table_name'], {'id': 'Inventory'}, dynamodb)
        if not item or item['update_status'] != 'RUNNING':
            if shopify_api.start_bulk_operation():
                LOGGER.info('Shopify bulk operation created')
                update_dynamodb(dynamodb, 'RUNNING')
                update_event_trigger(events_handler, 'rate(10 minutes)')
            else:
                LOGGER.error('Failed to start Shopify bulk operation')
                update_event_trigger(events_handler, 'rate(10 minutes)')
            return

        bulk_operation_status = shopify_api.current_bulk_operation()

        if bulk_operation_status == 'RUNNING':
            LOGGER.info('Waiting for Shopify bulk operation to complete')
            update_event_trigger(events_handler, 'rate(10 minutes)')
        elif bulk_operation_status == 'COMPLETED':
            products_text = shopify_api.get_products_text()

            if products_text:
                update_dynamodb(dynamodb, 'COMPLETED')
                update_event_trigger(events_handler, os.environ['cron_expression_for_next_day'])

                LOGGER.info('Starting product inventory mapping')
                map_product_inventory(products_text)
            else:
                LOGGER.error(f'Shopify did not return any products.')
                update_event_trigger(events_handler, 'rate(10 minutes)')
        else:
            LOGGER.error(f'Shopify returned invalid bulk operation status:\n{bulk_operation_status}')
            update_event_trigger(events_handler, 'rate(10 minutes)')

    except Exception as error: # pylint: disable=W0703
        LOGGER.error(f'Error while mapping inventory: {str(error)}', exc_info=True)
        # If there are too many requests already, start the next day
        update_event_trigger(events_handler, os.environ['cron_expression_for_next_day'])


def map_product_inventory(text):
    products_slices = process_transformation(text)

    for products in products_slices:
        if products['items']:
            LOGGER.info(f'Adding product mapping to queue')
            send_chunk_to_sqs(products)


def send_chunk_to_sqs(products):
    LOGGER.info(f"Sending products to queue...")

    payload = json.dumps(products)
    return MAPPING_QUEUE.send_message(MessageBody=payload)


def update_dynamodb(dynamodb, update_status):
    LOGGER.info('Updating dynamo table -- save state')
    update_item(os.environ['dynamo_table_name'], {
        'Key': {
            'id': 'Inventory'
        },
        'UpdateExpression': 'set update_status = :update_status',
        'ExpressionAttributeValues': {
            ':update_status': update_status
        },
        'ReturnValues': 'UPDATED_NEW'
    }, dynamodb)


def update_event_trigger(events_handler, trigger_expression):
    LOGGER.info(f'Updated the trigger event at {trigger_expression}')
    events_handler.update_trigger(TRIGGER_NAME, trigger_expression, True)
