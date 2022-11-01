# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.

# Runs startup processes
import netsuite.netsuite_environment_loader  # pylint: disable=W0611
import netsuite.api.transfers as netsuite_transfers

import logging
import os
import json
import asyncio
import boto3

import netsuite_adjustments_injection.transformers.process_adjustment as pa
import netsuite_adjustments_injection.helpers.util as util
import netsuite_adjustments_injection.helpers.sqs_consumer as sqs_consumer

from netsuite.api.item import get_product_by_sku
from time import time
from boto3.dynamodb.conditions import Key
from zeep.helpers import serialize_object
from newstore_adapter.connector import NewStoreConnector
from newstore_adapter.utils import get_extended_attribute

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

NEWSTORE_HANDLER = None
SQS_QUEUE = os.environ['SQS_QUEUE']
EVENT_ID_CACHE = os.environ.get('EVENT_ID_CACHE')
EVENT_ID_CACHE_CLEARED = False
DYNAMO_SCAN_LIMIT = int(os.environ.get('DYNAMO_SCAN_LIMIT', 50))
DYNAMO_TABLE = None
DAY_IN_SECONDS = 60 * 60 * 24

"""
Receives event payloads from an SQS queue. The payload is taken from the order
event stream, detailed here:
    https://apidoc.newstore.io/newstore-cloud/hooks_eventstream.html
Event Type: inventory_transaction.adjustment_created
"""


def handler(_event, context):
    LOGGER.info(f'Beginning queue retrieval...')
    global NEWSTORE_HANDLER
    newstore_creds = util.get_newstore_config()
    NEWSTORE_HANDLER = NewStoreConnector(tenant=newstore_creds['tenant'], context=context,
                                         username=newstore_creds['username'], password=newstore_creds['password'],
                                         host=newstore_creds['host'], raise_errors=True)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = sqs_consumer.consume(process_inventory, SQS_QUEUE)
    loop.run_until_complete(task)
    loop.stop()
    loop.close()


async def process_inventory(message):
    LOGGER.info(f"Message to process: \n {json.dumps(message, indent=4)}")
    adjustment_event = message['payload']

    if await event_already_received(f"{adjustment_event['id']}-{adjustment_event['chunk_number']}"):
        LOGGER.info("Event was already processed, skipping")
        return True

    store, products_info = get_store_and_products_from_nom(adjustment_event['items'],
                                                           adjustment_event['fulfillment_node_id'])
    inventory_transfer = pa.transform_inventory_transfer(adjustment_event, products_info, store)
    is_success, result = netsuite_transfers.create_inventory_transfer(inventory_transfer)

    if is_success:
        LOGGER.info("Inventory Transfer successfully created in NetSuite: " \
                    f"\n{json.dumps(serialize_object(result), default=util.json_serial)}")
        await mark_event_as_received(f"{adjustment_event['id']}-{adjustment_event['chunk_number']}")
    else:
        LOGGER.error(f'Error creating Inventory Transfer in NetSuite: {result}')

    return is_success


def get_store_and_products_from_nom(items, fulfillment_node_id):
    output = []
    product_ids = {item['product_id']: item['quantity'] for item in items}

    store_id = util.get_nws_location_id(fulfillment_node_id)
    store = util.get_store(NEWSTORE_HANDLER, store_id)

    for product_id in product_ids:
        product = util.get_product(NEWSTORE_HANDLER, product_id, store['catalog'], store['locale'])
        assert product, f"Product with ID {product_id} couldn't be fetched from NOM."

        netsuite_internal_id = get_extended_attribute(product.get('extended_attributes', []), 'variant_nsid')
        if netsuite_internal_id:
            LOGGER.info(f'Product NetSuite internal id {netsuite_internal_id} found for product {product_id}')
            output.append({
                'netsuite_internal_id': netsuite_internal_id,
                'quantity': product_ids[product_id]
            })
        else:
            LOGGER.info(
                'NetSuite internal id not found on NewStore for Item/Product {product_id}. Fallback to NetSuite sku lookup.')
            netsuite_item = get_product_by_sku(product_id)
            if netsuite_item:
                output.append({
                    'netsuite_internal_id': netsuite_item.internalId,
                    'quantity': product_ids[product_id]
                })
            else:
                raise Exception(f'Item/Product {product_id} not found on NetSuite.')

    return store, output


async def event_already_received(event_id):
    event_id_cache_table = get_dynamo_table()

    global EVENT_ID_CACHE_CLEARED
    if not EVENT_ID_CACHE_CLEARED:
        clear_old_events(dynamo_table=event_id_cache_table, days=7)
        EVENT_ID_CACHE_CLEARED = True  # We will limit this to clearing once per instantiation to limit overhead

    response = event_id_cache_table.scan(
        FilterExpression=Key('id').eq(event_id),
        Limit=DYNAMO_SCAN_LIMIT)

    if response['Items']:
        return True

    while 'LastEvaluatedKey' in response:
        response = event_id_cache_table.scan(
            FilterExpression=Key('id').eq(event_id),
            Limit=DYNAMO_SCAN_LIMIT,
            ExclusiveStartKey=response['LastEvaluatedKey'])
        if response['Items']:
            return True
    return False


async def mark_event_as_received(event_id):
    event_id_cache_table = get_dynamo_table()
    event_id_cache_table.put_item(
        Item={
            'id': event_id,
            'timestamp': int(time())
        },
        ConditionExpression='attribute_not_exists(id)'
    )


def clear_old_events(dynamo_table, days):
    LOGGER.warning(f'Clearing event cache more than {days} days old')

    timestamp_threshold = int(time() - (days * DAY_IN_SECONDS))
    LOGGER.info(f"timestamp_threshold {timestamp_threshold}")
    response = dynamo_table.scan(
        FilterExpression=Key('timestamp').lt(timestamp_threshold))
    data = response['Items']

    while 'LastEvaluatedKey' in response:
        response = dynamo_table.scan(
            FilterExpression=Key('timestamp').lt(timestamp_threshold),
            ExclusiveStartKey=response['LastEvaluatedKey'])
        data.extend(response['Items'])

    LOGGER.info(f'Found {len(data)} results: {data}')

    for event_row in data:
        dynamo_table.delete_item(Key={'id': event_row['id']})


def get_dynamo_table():
    global DYNAMO_TABLE
    if not DYNAMO_TABLE:
        event_id_cache_client = boto3.resource('dynamodb')
        DYNAMO_TABLE = event_id_cache_client.Table(EVENT_ID_CACHE)
    return DYNAMO_TABLE
