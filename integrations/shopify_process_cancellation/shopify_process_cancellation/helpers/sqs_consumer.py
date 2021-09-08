# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.
import os
import json
import logging
from lambda_utils.sqs.SqsHandler import SqsHandler

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
MAX_MESSAGE_QUEUE_SIZE = int(os.environ.get('MAX_MESSAGE_QUEUE_SIZE'))


async def consume(process, queue_name):
    sqs_handler = SqsHandler(queue_name)

    current_queue_size = sqs_handler.get_messages_count()
    number_of_messages_to_consume = min(MAX_MESSAGE_QUEUE_SIZE, current_queue_size)
    LOGGER.info(f'Number of messages enqueued: {current_queue_size}, number_of_messages_to_consume: {number_of_messages_to_consume}')
    while number_of_messages_to_consume > 0:
        LOGGER.info(f'Getting message from queue (number of messages still to be read: {number_of_messages_to_consume})')
        messages = sqs_handler.get_message()
        LOGGER.info(f"Message: {json.dumps(messages, indent=4)}")
        if 'Messages' not in messages:
            LOGGER.info('No message pulled from the queue...')
            break
        # Recipt with which we'll delete the message on success
        receipt_handle = messages['Messages'][0]['ReceiptHandle']
        # Trim message down to just the fin_trans data
        message = json.loads(messages['Messages'][0]['Body'])
        # Process the message w/ NetSuite
        LOGGER.info(f'Processing item for order {message["order"]["id"]}')
        try:
            result = await process(message)
            if result:
                # If return is True we remove, else we don't so it may be processed on next run
                try:
                    response = sqs_handler.delete_message(receipt_handle)
                except Exception as ex: # pylint: disable=broad-except
                    LOGGER.warning(f"Message wasn't deleted due to: {ex}")
                else:
                    LOGGER.info(f'Message deleted from the queue {response}')
        except Exception as e: # pylint: disable=broad-except
            LOGGER.error(f'Exception on order {message["order"]["id"]} details: {str(e)}', exc_info=True)
        number_of_messages_to_consume -= 1
    LOGGER.info('Execution ended normally.')
