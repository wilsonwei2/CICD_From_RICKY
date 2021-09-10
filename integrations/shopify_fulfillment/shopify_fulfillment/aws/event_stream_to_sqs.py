# -*- coding: utf-8 -*-
import os
import json
import asyncio
import logging
from datetime import datetime
from lambda_utils.sqs.SqsHandler import SqsHandler

LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOG_LEVEL)
SQS_SHOPIFY_FULFILLMENT = os.environ.get('SQS_SHOPIFY_FULFILLMENT')


def handler(event, _):
    '''
    Receives AWS events and send it to the SQS queue
    '''
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(process_event(event))
    loop.stop()
    loop.close()

    return {
        'statusCode': 200
    }


async def process_event(event):
    event_body = json.loads(event.get('body', {}))
    if not event_body:
        LOGGER.info("Empty event received")
        return True

    LOGGER.info(f'Event received: {event_body}')

    order = event_body['payload']
    order['published_at'] = event_body['published_at']
    event_type = event_body['name']

    message = {
        'order': order
    }

    if event_type == 'fulfillment_request.items_completed':
        if event_body.get('payload', {}).get('service_level') == 'IN_STORE_HANDOVER':
            LOGGER.info('Received a fulfillment_request.items_completed message with a service level of'
                        ' IN_STORE_HANDOVER. Will not process.')
            return True

        if is_historical_fulfillment(order):
            LOGGER.info('Received historical order...ignored')
            return True

        queue_list = [SQS_SHOPIFY_FULFILLMENT]
    else:
        LOGGER.warning(f'Received an unsupported event type: {event_type}')
        return True

    for queue_name in queue_list:
        sqs_handler = SqsHandler(queue_name=queue_name)
        sqs_handler.push_message(message_group_id=message['order']['id'], message=json.dumps(message))
        LOGGER.debug(f'Message pushed to SQS: {sqs_handler.queue_name}')

    return True

def is_historical_fulfillment(payload):
    items = payload.get('items', [])
    if len(items) > 0:
        item = items[0]
        if item.get('shipped_at'):
            shipped_at = datetime.fromisoformat(item['shipped_at'][0:19])
            live_date = datetime.fromisoformat('2021-09-14T00:00:00')
            return shipped_at < live_date

    return False
