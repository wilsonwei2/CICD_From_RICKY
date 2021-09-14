# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.
import os
import json
import logging
import asyncio

from shopify_inventory_update.handlers.shopify_handler import ShopifyConnector
from shopify_inventory_update.handlers.sqs_handler import SqsHandler
from shopify_inventory_update.handlers.lambda_handler import stop_before_timeout
from shopify_inventory_update.handlers.dynamodb_handler import (
    get_item,
    update_item
)

from pom_common.shopify import ShopManager

LOGGER = logging.getLogger(__name__)
LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER.setLevel(LOG_LEVEL)
BLOCK_CONCURRENT_EXECUTION = bool(os.environ.get('BLOCK_CONCURRENT_EXECUTION', 'False'))
CONCURRENT_EXECUTION_BLOCKED_KEY = 'concurrent_execution_blocked'
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'frankandoak-availability-job-save-state')
SQS_HANDLER = None
WORKER_TRIGGER_DEFAULT_NAME = 'shopify_availability_export_worker'
STOP_BEFORE_TIMEOUT = 60000

TENANT = os.environ.get('TENANT', 'frankandoak')
STAGE = os.environ.get('STAGE', 'x')
REGION = os.environ.get('REGION', 'us-east-1')


def handler(event, context):
    """
    Arguments:
        event {dic} -- Lambda event
        context {object} -- Lambda object

    Returns:
        string -- Result string of process
    """
    if BLOCK_CONCURRENT_EXECUTION:
        if _is_blocked():
            return 'Execution blocked'
        else:
            _set_blocked_state(True)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        future = asyncio.ensure_future(_sync_inventory(loop, context))
        loop.run_until_complete(future)
        loop.stop()
        loop.close()
    finally:
        _set_blocked_state(False)

    return 'Finished'


async def _sync_inventory(loop, context):
    """Syncs the invetory with shopify by pulling messages from a queue and
        updating the quantity of the variants in shopify.
        This handler can have more than one variant in each queue message but
        will always process on-by-one to shopify
    Arguments:
        loop {EventLoop} -- Async event loop
    """
    shop_manager = ShopManager(TENANT, STAGE, REGION)
    shopify_connectors = {}

    for shop_id in shop_manager.get_shop_ids():
        shopify_config = shop_manager.get_shop_config(shop_id)

        shopify_connectors[shopify_config['currency']] = ShopifyConnector(
            shopify_config['username'],
            shopify_config['password'],
            shopify_config['shop']
        )

    global sqs_handler
    sqs_handler = SqsHandler(
        os.environ.get("SQS_NAME")
    )

    message_count = await sqs_handler.get_messages_count()
    if message_count <= 0:
        LOGGER.info('No more messages to process... exiting->()')
        return
    LOGGER.info('%s available in the queue...', str(message_count))

    while message_count > 0:
        if stop_before_timeout(context, STOP_BEFORE_TIMEOUT, LOGGER):
            return 'Stopping before timeout'

        messages = await sqs_handler.get_message()
        if messages.get('Messages'):

            for message in messages['Messages']:
                if stop_before_timeout(context, STOP_BEFORE_TIMEOUT, LOGGER):
                    return 'Stopping before timeout'

                receipt_handle = message['ReceiptHandle']
                success = True
                products = json.loads(message['Body'])
                LOGGER.debug(f'Raw products from SQS:\n{products}')
                '''
                [{
                    'atp': 19,
                    'shopify_inventory_id': {
                        'cad': '42467871719580',
                        'usd': '42467871719581'
                    }
                    'location_ids': {
                        'cad': '61464969372',
                        'usd': '62202544304'
                    }
                }, ...]
                '''
                if len(products) > 0:
                    products_by_location = defining_product_by_location(products)

                    for location_id, country_products in products_by_location.items():
                        try:
                            await _update_variant_at_shopify(country_products, shopify_connectors, location_id)
                        except:
                            success = False

                if success:
                    await sqs_handler.delete_message(receipt_handle)

        message_count = await sqs_handler.get_messages_count()
        LOGGER.info('%s available in the queue...',
                    str(message_count))

    return 'Sync of inventory with shopify complete'


def defining_product_by_location(products):
    products_by_location = {}

    for value in products:
        location_ids = value['location_ids']

        for currency, location_id in location_ids.items():
            if not location_id in products_by_location:
                products_by_location[location_id] = {}

            if not currency in products_by_location[location_id]:
                products_by_location[location_id][currency] = []

            shopify_inventory_id = None
            if value.get('shopify_inventory_ids', {}).get(currency):
                shopify_inventory_id = value.get('shopify_inventory_ids', {}).get(currency)

            if shopify_inventory_id:
                products_by_location[location_id][currency].append({
                    'inventory_item_id': str(shopify_inventory_id),
                    'atp': value['atp']
                })

    return products_by_location


async def _update_variant_at_shopify(products, shopify_connectors, location_id):
    LOGGER.debug(f'Updating products {products} at location {location_id}')

    for currency, shopify_connector in shopify_connectors.items():
        currency = currency.lower()
        if currency in products:
            try:
                LOGGER.info(f'Process products for {currency}')
                country_products = await _create_deltas_for_inventory(products[currency], shopify_connector, location_id)
                if len(country_products) > 0:
                    LOGGER.debug(f'Sending deltas to Shopify ({currency}) location {location_id}: {country_products}')
                    await shopify_connector.update_inventory_quantity_graphql(country_products, location_id)
                else:
                    LOGGER.info(f'No deltas created for Shopify ({currency}) - no update send.')
            except Exception:
                LOGGER.exception(f'Failed to process bulk variant update for Shopify ({currency})')
                raise


async def _create_deltas_for_inventory(products, shopify_connector, location_id):
    LOGGER.info('Fetching inventory levels from Shopify')
    inventory_shopify = _transform_to_dictionary_inventory_map(await shopify_connector.get_inventory_quantity(products, location_id))
    LOGGER.info('Response from transform ')
    LOGGER.info(inventory_shopify)
    for product in products:
        formated_variant = f'gid://shopify/InventoryItem/{product["inventory_item_id"]}'
        if formated_variant in inventory_shopify:
            product['delta'] = product['atp'] - inventory_shopify[formated_variant]
    return products


def _transform_to_dictionary_inventory_map(inventory_shopify_response):
    result = {}
    LOGGER.info(f'Inventory Shopify Response: {inventory_shopify_response}')
    if inventory_shopify_response is not None:
        for inventory in inventory_shopify_response:
            id_inventory = inventory.get('item', {}).get('id')
            if id_inventory:
                result[id_inventory] = inventory['available']
    return result


def _set_blocked_state(blocked):
    update_item(table_name=DYNAMODB_TABLE_NAME, schema={
        'Key': {
            'identifier': str(CONCURRENT_EXECUTION_BLOCKED_KEY)
        },
        'UpdateExpression': 'set blocked=:value',
        'ExpressionAttributeValues': {
            ':value': str(blocked)
        }
    })


def _is_blocked():
    response = get_item(table_name=DYNAMODB_TABLE_NAME, item={
        'identifier': str(CONCURRENT_EXECUTION_BLOCKED_KEY)
    })

    if response is None:
        return False

    if 'blocked' in response:
        return response['blocked'] == 'True'

    return False
