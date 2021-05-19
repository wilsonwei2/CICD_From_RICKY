# -*- coding: utf-8 -*-
# Copyright (C) 2020-21 NewStore, Inc. All rights reserved.
import os
import json
import logging
import asyncio

from newstore_adapter.connector import NewStoreConnector
from shopify_inventory_update.handlers.lambda_handler import start_lambda_function
from shopify_inventory_update.handlers.dynamodb_handler import (
    get_item,
    update_item
)

LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOG_LEVEL)

TENANT = os.environ['TENANT'] or 'frankandoak'
LAST_UPDATED_KEY = 'last_updated_at'
DYNAMODB_TABLE_NAME = 'frankandoak-availability-job-save-state'

def handler(event, context):
    """

    Arguments:
        event {dic} -- Lambda event
        context {object} -- Lambda object

    Returns:
        string -- Result string of process
    """
    LOGGER.debug('Event : %s', json.dumps(event))
    is_full = False

    TRIGGER_NAME = None
    if 'resources' in event:
        TRIGGER_NAME = event['resources'][0].split('/')[1]
    ## ADDING TRIGGER NAME AND USING IT AS A RESOURCE FOR FULL RUN.

    if TRIGGER_NAME is not None:
        LOGGER.info(f'Trigger name -- {TRIGGER_NAME}')

    if TRIGGER_NAME is not None and 'full_export' in TRIGGER_NAME:
        is_full = True
        LOGGER.info(f'Running a full export with Trigger Name -- {TRIGGER_NAME}')
        LOGGER.info('Updating the dynamoDB Updated value to 0 for full export')
        save_last_updated_to_dynamo_db(str(0))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_create_export_availabilities_job(context, is_full))
    loop.stop()
    loop.close()
    return result


async def _create_export_availabilities_job(context, is_full: False):
    """Create an availability export job at newstore

    Returns:
     string -- string with result export job id
    """
    ns_handler = NewStoreConnector(TENANT, context)
    export = ns_handler.start_availability_export(_get_last_entry_object(is_full))

    ## And the request response is forwarded to Next lambda -- availabilities to queue
    force_wait_process_job = bool(os.environ.get('FORCE_CHECKING_FOR_JOB', 'False'))
    LOGGER.info('Response received from the call - next line export from the call')
    LOGGER.info(export)

    if force_wait_process_job:
        lambda_name = os.environ.get('PUSH_TO_QUEUE_LAMBDA_NAME', 'inventory-push-to-queue')
        LOGGER.debug(f'Starting {lambda_name} lambda')
        await start_lambda_function(
            lambda_name,
            payload=export
        )

    return export


def _get_last_entry_object(is_full):
    """Gets the last entry for s3. Should be the highest number in a S3 file

    Returns:
        string -- string with the integer of the highest number found
    """
    max_key = 0

    if is_full:
        return max_key

    key = {
        'identifier': str(LAST_UPDATED_KEY)
    }

    response = get_item(table_name=DYNAMODB_TABLE_NAME, item=key)

    if response is None:
        return max_key

    if 'last_value' in response:
        max_key = int(response['last_value'])
    else:
        max_key = 0

    return max_key

def save_last_updated_to_dynamo_db(last_updated_at):
    key = {
        'identifier': str(LAST_UPDATED_KEY)
    }

    expression_attribute_values = {
        ':value': str(last_updated_at)
    }

    update_expression = "set last_value=:value"

    schema = {
        'Key': key,
        'UpdateExpression': str(update_expression),
        'ExpressionAttributeValues': expression_attribute_values
    }

    update_item(table_name=DYNAMODB_TABLE_NAME, schema=schema)
