import os
import json
import logging
import asyncio
from lambda_utils.sqs.SqsHandler import SqsHandler
from .handlers.s3_handler import S3Handler

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

EVENTS_TYPE = [
    'fulfillment_request.items_completed',
    'order.items_cancelled'
]


def handler(event, context): # pylint: disable=unused-argument
    """
    Arguments:
        event {dic} -- Lambda event
        context {object} -- Lambda object

    Returns:
        string -- Result string of process
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_save_event_handler(event))
    loop.stop()
    loop.close()
    return result


async def _save_event_handler(event: dict) -> dict:
    """
    Start of the lambda handler
    :param event: Shopify webhook order json
    :param context: function context

    This function takes two triggers -> one from S3 and one from event stream webhook
    """
    LOGGER.info(f'Received event: {json.dumps(event)}')
    # S3 put_item trigger
    if 'Records' in event:
        if len(event.get('Records', [])) < 1:
            LOGGER.info('No records to process.')
            return
        file_details = event['Records'][0]
        s3_handler = S3Handler(record=file_details)
        if not s3_handler.validate_exists():
            LOGGER.exception(f'No file {s3_handler.getS3BucketKey()} found in bucket {s3_handler.getS3BucketName()}.')
            return
        file_contents = json.loads(s3_handler.getS3File()['data'])
        body = {
            'name': os.environ['CANCELLED_EVENT_NAME'],
            'payload': file_contents
        }
    # event stream trigger
    else:
        body = event['body']
        body = json.loads(body)
        if not _validate_event_type(body):
            LOGGER.info(
                'Received event is not on the event type to be consumed...'
            )
            return {
                "statusCode": 200
            }
    result = await _save_event(body)
    if result:
        return {
            "statusCode": 200
        }
    return {
        "statusCode": 500
    }


def _validate_event_type(body: dict) -> bool:
    return body['name'] in EVENTS_TYPE


async def _save_event(event: dict) -> bool:
    try:
        # only send emails for delivery orders
        if event['name'] == 'fulfillment_request.items_completed' and \
                'IN_STORE' in event['payload']['service_level']:
            LOGGER.info('In store fulfillment, ignoring...')
            return True
        await _drop_to_queue(
            event, SqsHandler(os.environ['SAILTHRU_QUEUE']))
        return True
    except Exception: # pylint: disable=broad-except
        LOGGER.exception('Something went wrong sending message to queue')
        return False


async def _drop_to_queue(event, sqs_handler):
    return sqs_handler.push_message(message=json.dumps(event), message_group_id=event['payload']['id'])
