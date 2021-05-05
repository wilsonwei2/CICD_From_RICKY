# -*- coding: utf-8 -*-
# Copyright (C) 2020-21 NewStore, Inc. All rights reserved.

import asyncio
import io
import json
import logging
import os
import zipfile
import aiohttp

from param_store.client import ParamStore
from newstore_adapter.connector import NewStoreConnector
from shopify_inventory_update.handlers.lambda_handler import start_lambda_function
from shopify_inventory_update.handlers.shopify_handler import ShopifyConnector, RateLimiter
from shopify_inventory_update.handlers.sqs_handler import SqsHandler
from shopify_inventory_update.handlers.events_handler import EventsHandler
from shopify_inventory_update.handlers.s3_handler import S3Handler
from shopify_inventory_update.handlers.dynamodb_handler import (
    update_item,
    get_item
)

LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOG_LEVEL)

WORKER_TRIGGER_DEFAULT_NAME = 'availabilities_to_queue_worker'
MAP_FILE_VARIANTS_SKU = 'sku_to_variant_id_map_dict.json'
DYNAMODB_TABLE_NAME = 'frankandoak-availability-job-save-state'
JOB_STATE_KEY = 'current_job_state'
LAST_UPDATED_KEY = 'last_updated_at'

LOCATIONS_MAP_INFO = None
LOCATIONS_MAP = None
SHOPIFY_CONECTOR = None
PARAM_STORE = None

TENANT = os.environ['TENANT'] or 'frankandoak'
STAGE = os.environ['STAGE'] or 'x'


def handler(event, context):
    """
    Arguments:
        event {dic} -- Lambda event
        context {object} -- Lambda object

    Returns:
        string -- Result string of process
    """
    global PARAM_STORE, LOCATIONS_MAP_INFO
    if not PARAM_STORE:
        PARAM_STORE = ParamStore(TENANT, STAGE)
    if not LOCATIONS_MAP_INFO:
        LOCATIONS_MAP_INFO = json.loads(PARAM_STORE.get_param('shopify/locations_map_info'))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_save_to_queue_availabilities(context, event))
    loop.stop()
    loop.close()
    return result


async def _map_locations_if_not(session):
    global LOCATIONS_MAP
    if not LOCATIONS_MAP:
        LOCATIONS_MAP = {}
        global SHOPIFY_CONECTOR
        locations = await SHOPIFY_CONECTOR.get_locations(session)
        for location in locations:
            if LOCATIONS_MAP_INFO.get(location.get('zip')):
                LOCATIONS_MAP[LOCATIONS_MAP_INFO.get(location.get('zip'))] = location.get('id')


def get_availability_job_id():
    key = {
        'identifier': str(JOB_STATE_KEY)
    }
    response = get_item(table_name=DYNAMODB_TABLE_NAME, item=key)
    return response

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


def save_state_in_dynamodb(availability_export_id, export_job_state, upto_date):
    job_id = availability_export_id

    key = {
        'identifier': str(JOB_STATE_KEY)
    }

    job_state = export_job_state

    expression_attribute_values = {
        ':job_state': str(job_state),
        ':job_id': str(job_id),
        ':upto_date': str(upto_date)
    }

    update_expression = "set availability_export_id=:job_id, availability_job_state=:job_state, availability_data_upto_date=:upto_date"

    schema = {
        'Key': key,
        'UpdateExpression': str(update_expression),
        'ExpressionAttributeValues': expression_attribute_values
    }

    update_item(table_name=DYNAMODB_TABLE_NAME, schema=schema)


async def _save_to_queue_availabilities(context, event):
    """Validates the type of the request and sends it to respective handler

    Arguments:
        event {dic} -- lambda event dictionary

    Returns:
        dic -- run result. Can be a simple dic or a API gateway rest result
    """
    if 'availability_export_id' in event:
        LOGGER.info('Saving the availability job id in dynamodb and recalling again in 5 mins')
        save_state_in_dynamodb(event['availability_export_id'], 'processing', 'no')
        events_handler = EventsHandler()
        await events_handler.update_trigger(
            os.environ.get('TRIGGER_NAME', WORKER_TRIGGER_DEFAULT_NAME), "rate(5 minutes)", True)
        return {'result': 'Retrying again after 5 minute'}
    else:
        response = get_availability_job_id()
        if response['availability_export_id'] and response['availability_job_state']:
            LOGGER.info(f"Found current job from dynamo db table - as -- {str(response['availability_export_id'])} and previoud state -- {response['availability_job_state']}")
            ## Possible inputs -- availability id respoinse
            return await wait_job_and_process_variants(context, response)
        else:
            LOGGER.info('Could not find which method to process variants to queue; make sure it is a api gateway request or a lambdas invocation with the id inside.')


async def wait_job_and_process_variants(context, event):
    """Gets export job to see if it can process availabilities.
    If not finised waits 1 min and invokes this lambda to make another run.

    Arguments:
        event {dic} -- Lambda Event dic containig the export job id reference
    """
    if event['availability_data_upto_date'] == 'yes':
        LOGGER.info('Exported all the data to shopify -- ignoring the job.')
        return {'result': 'All variants exported to the queue'}

    events_handler = EventsHandler()
    ns_handler = NewStoreConnector(TENANT,  context)

    '''
    Example
    {
        "availability_export_id": "684d48df-28e0-459b-bd1f-1d32035e72ca"
    }
    '''
    export_job = ns_handler.get_availability_export(event['availability_export_id'])

    if export_job.get('state') == 'processing':
        LOGGER.info('Job is still processing calling again in 5 mins')
        events_handler = EventsHandler()
        await events_handler.update_trigger(
            os.environ.get('TRIGGER_NAME', WORKER_TRIGGER_DEFAULT_NAME), "rate(5 minutes)", True)
        return {'result': 'Retrying again after 5 minute'}

    if 'last_updated_at' in export_job and int(export_job['last_updated_at']) == 0:
        LOGGER.info('Exported all the data to shopify -- ignoring the job.')
        save_state_in_dynamodb(event['availability_export_id'], 'finished', 'yes')
        await events_handler.update_trigger(
            os.environ.get('TRIGGER_NAME', WORKER_TRIGGER_DEFAULT_NAME), "rate(1 hour)", True)
        return {'result': 'All variants exported to the queue'}

    if export_job.get('state') == 'finished' and event['availability_data_upto_date'] == 'no':
        link = str(export_job['link'])
        last_updated_at = str(export_job['last_updated_at'])
        variants = await read_variants_from_export_file(link, last_updated_at)
        await _process_variants_to_queue(variants)
        LOGGER.info(f'Start inventory push to shopify next')
        await start_lambda_function(
            os.environ.get('PUSH_TO_SHOPIFY_LAMBDA_NAME',
                           'frankandoak-inventory-push-to-shopify')
        )
        await events_handler.update_trigger(
            os.environ.get('TRIGGER_NAME', WORKER_TRIGGER_DEFAULT_NAME), "rate(1 hour)", True)
        save_state_in_dynamodb(event['availability_export_id'], 'finished', 'yes')
        LOGGER.info('Getting export job id...')
        return {'result': 'All variants exported to the queue'}


## Location where all the operations happen.
async def read_variants_from_export_file(file_url, last_updated_at):
    """Gets a file from a URl, saves it to an S3 and returns the file contents

    Arguments:
        file_url {string} -- The file URL
        last_updated_at {string} -- The last updated value used to save the file in s3

    Returns:
        dic -- Saved file data in dictionary
    """
    s3_handler = S3Handler(
        bucket_name=os.environ["S3_BUCKET_NAME"],
        key_name='helpers/exports/{last_updated_at}/inventory_levels.json'.
            format(last_updated_at=last_updated_at)
    )
    variants = None

    save_last_updated_to_dynamo_db(last_updated_at)

    file = await _get_file(url=file_url)

    LOGGER.info('Uploading file to s3')

    # s3_handler.put_object(data=file)

    variants = json.loads(file)

    s3_handler.put_object(data=json.dumps(variants))

    return variants


async def _process_variants_to_queue(variants):
    """Puts the variants into a message and drops it to a queue

    Arguments:
        variants {dic} -- Variants list

    Returns:
        object -- Result Drop to queue message object
    """
    LOGGER.info('Processing %i variants from the currently exported job. ',
                (len(variants)))

    sqs_handler = SqsHandler(queue_name=os.environ["SQS_NAME"])

    shopify_config = json.loads(PARAM_STORE.get_param('shopify'))
    global SHOPIFY_CONECTOR
    SHOPIFY_CONECTOR = ShopifyConnector(
        shopify_config['username'],
        shopify_config['password'],
        shopify_config['shop']
    )

    async with aiohttp.ClientSession() as client:
        session = RateLimiter(client)
        await _map_locations_if_not(session)

    LOGGER.info('Processing variants from the json')

    shopify_inventory_item_list = {}
    counter = 0

    for variant in variants:
        atp = int(variant['atp'])
        shopify_inventory_id = None
        current_atp = None
        current_location_id = None
        current_list_item = {}

        if 'external_identifiers' in variant:
            if len(variant['external_identifiers']) > 0:
                external_identifier = variant['external_identifiers'][0]
                identifiers = external_identifier['identifiers']

                if 'shopify_inventory_item_id' in identifiers:
                    shopify_inventory_id = identifiers['shopify_inventory_item_id']

        if variant.get('fulfillment_node_id') in LOCATIONS_MAP:
            current_location_id = LOCATIONS_MAP[variant['fulfillment_node_id']]

        if shopify_inventory_id is None or current_location_id is None:
            continue

        if len(shopify_inventory_item_list) == 100:
            await _drop_to_queue(sqs_handler, shopify_inventory_item_list)
            counter = counter + 1
            LOGGER.info(f'Pushed message number {counter} to queue {sqs_handler.queue_name}')
            shopify_inventory_item_list.clear()

        if shopify_inventory_id in shopify_inventory_item_list:
            current_atp = atp + shopify_inventory_item_list[shopify_inventory_id]
        else:
            current_atp = atp

        shopify_inventory_item_list[shopify_inventory_id] = {
            'atp': current_atp,
            'location_id': current_location_id
        }

    if len(shopify_inventory_item_list) > 0:
        await _drop_to_queue(sqs_handler, shopify_inventory_item_list)
        LOGGER.info(f'Pushed last message to queue {sqs_handler.queue_name}')
        shopify_inventory_item_list.clear()


async def _drop_to_queue(sqs_handler, message_availability):
    await sqs_handler.push_message(message=json.dumps(message_availability))


async def _get_file(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url=url) as response:
            response.raise_for_status()
            response_data = await response.read()
            if '.zip' in url:
                with io.BytesIO(response_data) as tf:
                    # rewind the file
                    tf.seek(0)
                    # Read the file as a zipfile and process the members
                    with zipfile.ZipFile(tf, mode='r') as zipf:
                        for subfile in zipf.namelist():
                            if subfile.startswith('__MACOSX'):
                                continue
                            # Assumes only one.
                            return zipf.read(subfile)

            LOGGER.info("Responding with data from zip file")
            return response_data
