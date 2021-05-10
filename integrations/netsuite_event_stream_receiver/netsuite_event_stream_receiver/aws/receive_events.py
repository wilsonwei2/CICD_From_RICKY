# -*- coding: utf-8 -*-
import os
import json
import asyncio
import logging
from lambda_utils.sqs.SqsHandler import SqsHandler
from netsuite_event_stream_receiver.aws.graphql_query import ORDER_VALIDATION_QUERY
from netsuite_event_stream_receiver.handlers.newstore_handler import NShandler
from param_store.client import ParamStore

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
SQS_CASH_SALE = os.environ.get('SQS_CASH_SALE')
SQS_SALES_ORDER = os.environ.get('SQS_SALES_ORDER')
SQS_TRANSFER_ORDER_QUEUE = os.environ.get('SQS_TRANSFER_ORDER_QUEUE')
SQS_INVENTORY_TRANSFER = os.environ.get('SQS_INVENTORY_TRANSFER')
SQS_RETURN_PROCESSED = os.environ.get('SQS_RETURN_PROCESSED')
SQS_FULFILLMENT = os.environ.get('SQS_FULFILLMENT')
SQS_FULFILLMENT_ASSIGNED = os.environ.get('SQS_FULFILLMENT_ASSIGNED')
SQS_APPEASEMENT_REFUND = os.environ.get('SQS_APPEASEMENT_REFUND')
TENANT = os.environ.get('TENANT')
STAGE = os.environ.get('STAGE')
NEWSTORE_HANDLER = None

# Setting to define if a POS order should be injected as Sales Order in Netsuite
HANDLE_POS_ORDER_AS_SALES_ORDER = os.environ.get('HANDLE_POS_ORDER_AS_SALES_ORDER')

def handler(event, _):
    ###
    # Receives NOM events and send to the queue
    ###
    event_body = json.loads(event.get('body', {}))
    LOGGER.info(f'Event received: {event_body}')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(process_event(event))
    loop.stop()
    loop.close()

    return {
        'statusCode': 200
    }


async def process_event(event): #pylint: disable=too-many-branches
    event_body = json.loads(event.get('body', {}))
    if not event_body:
        LOGGER.info('Empty event received')
        return True

    payload = event_body['payload']
    payload['published_at'] = event_body['published_at']
    event_type = event_body['name']

    message = {
        'payload': payload
    }

    LOGGER.info(f'Event name -- {event_type}')

    if event_type == 'order.opened':
        external_id = payload.get('external_id')
        if external_id.startswith('HIST'):
            LOGGER.info(f'Ignore Historical order {external_id}')
            return True

        # A channel_type of 'web' or a shipping service level denotes that this is
        # not a cash sale, so should be handled as a sales order
        is_a_web_order = payload['channel_type'] == 'web'
        shipping_service_level = payload['items'][0].get('shipping_service_level', None)
        is_endless_aisle = bool(shipping_service_level and shipping_service_level != 'IN_STORE_HANDOVER')
        if is_a_web_order or is_endless_aisle or HANDLE_POS_ORDER_AS_SALES_ORDER in ('1', 't', 'true', 'yes'):
            queue_name = SQS_SALES_ORDER
        else:
            queue_name = SQS_CASH_SALE
    elif event_type == 'inventory_transaction.asn_created':
        queue_name = SQS_TRANSFER_ORDER_QUEUE
    elif event_type == 'inventory_transaction.items_received':
        queue_name = SQS_INVENTORY_TRANSFER
    elif event_type == 'return.processed':
        queue_name = SQS_RETURN_PROCESSED
    elif event_type == 'fulfillment_request.assigned':
        # PROD -- ISSUE -- Commenting due to eventstream late response time.
        # if await is_historical_or_instore(payload):
        #     return True

        queue_name = SQS_FULFILLMENT_ASSIGNED
    elif event_type == 'fulfillment_request.items_completed':
        #PROD -- ISSUE -- Commenting due to eventstream late response time.
        if await is_historical_order(payload['order_id']):
            LOGGER.info('Ignoring Fulfillment completed for Historical Order')
            return True

        if event_body.get('payload', {}).get('service_level') == 'IN_STORE_HANDOVER':
            LOGGER.info('Received a fulfillment_request.items_completed message with a service level of '
                        'IN_STORE_HANDOVER. Will not process.')
            return True
        queue_name = SQS_FULFILLMENT
    elif event_type == 'refund_request.issued':
        queue_name = SQS_APPEASEMENT_REFUND
    else:
        LOGGER.warning(f'Received an unsupported event type: {event_type}')
        return True

    push_message_to_sqs(queue_name, message)

    return True


def push_message_to_sqs(queue_name, message):
    sqs_handler = SqsHandler(queue_name=queue_name)
    sqs_handler.push_message(message_group_id=message['payload']['id'], message=json.dumps(message))
    LOGGER.info(f'Message pushed to SQS: {sqs_handler.queue_name}')


async def is_historical_or_instore(payload):
    if await is_historical_order(payload['order_id']):
        LOGGER.info('Ignoring Fulfillment assignment for Historical Order')
        return True

    if payload['service_level'] == 'IN_STORE_HANDOVER':
        LOGGER.info('Ignoring since the event is Instore Handover assignment')
        return True


async def is_historical_order(order_id):
    param_store = get_param_store()

    global NEWSTORE_HANDLER  # pylint: disable=W0603
    newstore_creds = json.loads(param_store.get_param('newstore'))

    NEWSTORE_HANDLER = NShandler(
        host=newstore_creds['host'],
        username=newstore_creds['username'],
        password=newstore_creds['password']
    )

    variables = {
        'id': order_id,
        'tenant': TENANT
    }

    order_data = await NEWSTORE_HANDLER.graphql_req(ORDER_VALIDATION_QUERY, variables)

    if order_data is not None:
        details = order_data['data']
        if 'order' in details:
            if details['order'] is None:
                return False
            if 'externalId' in details['order']:
                external_id = details['order']['externalId']
                return external_id.startswith('HIST')

        if 'order' in details:
            if 'isHistorical' in details['order']:
                is_historical_check = details['order']['isHistorical']
                return bool(is_historical_check)

    return False


def get_param_store():
    param_store = ParamStore(tenant=TENANT, stage=STAGE)
    return param_store
