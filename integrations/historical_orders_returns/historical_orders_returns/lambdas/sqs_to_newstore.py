import os
import logging
import json
import boto3
from newstore_adapter.connector import NewStoreConnector
from newstore_common.aws import init_root_logger

init_root_logger(__name__)
LOGGER = logging.getLogger(__name__)

SQS = boto3.resource("sqs", os.environ['REGION'])
QUEUE = SQS.get_queue_by_name(QueueName=os.environ['QUEUE_NAME']) # pylint: disable=no-member
TENANT = os.environ.get('TENANT', 'frankandoak')
STAGE = os.environ.get('STAGE', 'x')
TYPE = os.environ['TYPE']


def import_order_to_newstore(payload, ns_handler):
    newstore_response = ns_handler.fulfill_order(payload)

    LOGGER.debug(f'Response: {newstore_response}')
    return newstore_response


def import_return_to_newstore(order_id, payload, ns_handler):
    newstore_response = ns_handler.create_return(order_id, payload)

    LOGGER.debug(f'Response: {newstore_response}')
    return newstore_response


def handler(_, context):
    ns_handler = NewStoreConnector(
        tenant=TENANT,
        context=context
    )

    for count in range(50): # pylint: disable=too-many-nested-blocks
        messages = QUEUE.receive_messages(
            MaxNumberOfMessages=10,
            WaitTimeSeconds=0
        )

        LOGGER.info(f'Received next 10 messages from queue... iteration {count}')
        if len(messages) == 0:
            break

        for message in messages:
            try:
                body = json.loads(message.body)
                LOGGER.info(f'Processing Message: {message.message_id}')

                newstore_response = None
                if TYPE == 'order':
                    newstore_response = import_order_to_newstore(body, ns_handler)
                if TYPE == 'return':
                    newstore_response = import_return_to_newstore(body['order_id'], body['return'], ns_handler)

                if newstore_response:
                    LOGGER.info('Deleting message from queue...')
                    message.delete()

            except Exception as e: # pylint: disable=broad-except
                LOGGER.exception(e)


    return {
        "success": True
    }
