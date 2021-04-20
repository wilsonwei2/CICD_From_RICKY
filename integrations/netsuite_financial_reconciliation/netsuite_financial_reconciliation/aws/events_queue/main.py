# -*- coding: utf-8 -*-
from datetime import datetime
import os
import json
import asyncio
import logging
from lambda_utils.sqs.SqsHandler import SqsHandler
from param_store.client import ParamStore
from newstore_common.aws import init_root_logger

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
init_root_logger(__name__)

SQS_CASH_SALE = os.environ.get('SQS_CASH_SALE')
SQS_SALES_ORDER = os.environ.get('SQS_SALES_ORDER')
PARAM_STORE = None
NETSUITE_CONFIG = None
NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG = None


###
# Receives AWS events and based on the type send it to the right queue
###
def handler(event, context):  # pylint: disable=W0613
    LOGGER.info(f'Event received: {json.dumps(event, indent=4)}')

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(process_event(event))

    loop.stop()
    loop.close()

    return {
        'statusCode': 200
    }


def check_true(value):
    if not value:
        return False
    return value in ['1', 'yes', 'true', 1, True, 'TRUE']


def get_param_store():
    global PARAM_STORE  # pylint: disable=W0603
    if not PARAM_STORE:
        tenant = os.environ.get('TENANT_NAME')
        stage = os.environ.get('NEWSTORE_STAGE')
        PARAM_STORE = ParamStore(tenant=tenant,
                                 stage=stage)
    return PARAM_STORE


def get_netsuite_config():
    global NETSUITE_CONFIG  # pylint: disable=W0603
    if not NETSUITE_CONFIG:
        NETSUITE_CONFIG = json.loads(get_param_store().get_param('netsuite'))
    return NETSUITE_CONFIG


def get_newstore_to_netsuite_locations_config():
    global NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG # pylint: disable=W0603
    if not NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG:
        NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG = json.loads(
            get_param_store().get_param('netsuite/newstore_to_netsuite_locations'))
    return NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG


def is_after_golive_order(event_date):
    golive_date = get_netsuite_config().get('golive_date', '')[:19]
    event_date = event_date[:19]
    if golive_date:
        return datetime.strptime(golive_date, "%Y-%m-%dT%H:%M:%S") < datetime.strptime(event_date, "%Y-%m-%dT%H:%M:%S")
    return False


def is_store(store_id):
    try:
        return bool(get_newstore_to_netsuite_locations_config()[store_id])
    except Exception as ex:
        LOGGER.info(f'{store_id} is not a store or location is not mapped. {ex}')
        return False
    return False


async def process_event(event):
    event_body = json.loads(event.get('body', {}))
    if not event_body:
        LOGGER.info("Empty event received")
        return True

    if not is_after_golive_order(event_body['published_at']):
        LOGGER.info("Skipping order before Go-Live date.")
        return True

    payload = event_body['payload']
    event_type = event_body['name']


    queue_list = []
    if event_type == 'order.opened':
        external_id = payload.get('external_id')
        if external_id.startswith("HIST"):
            LOGGER.info(f"Ignore Historical order {external_id}")
            return True
        # A channel_type of 'web' or a shipping service level denotes that this is
        # not a cash sale, so should be handled as a sales order
        is_a_web_order = payload['channel_type'] == 'web'
        shipping_service_level = payload['items'][0].get('shipping_service_level', None)
        is_endless_aisle = bool(shipping_service_level and shipping_service_level != 'IN_STORE_HANDOVER')
        if is_a_web_order or is_endless_aisle:
            queue_list = [SQS_SALES_ORDER]
        else:
            queue_list = [SQS_CASH_SALE]
    else:
        LOGGER.warning(f'Received an unsupported event type: {event_type}')
        return True

    for queue_name in queue_list:
        sqs_handler = SqsHandler(queue_name=queue_name)
        sqs_handler.push_message(message_group_id=payload['id'], message=json.dumps(event_body))
        LOGGER.info(f'Message pushed to SQS: {sqs_handler.queue_name}')

    return True
