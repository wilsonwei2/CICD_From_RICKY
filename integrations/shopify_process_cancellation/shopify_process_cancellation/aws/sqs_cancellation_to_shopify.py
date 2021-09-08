# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.
import logging
import os
import json
import asyncio
import shopify_process_cancellation.helpers.sqs_consumer as sqs_consumer
from shopify_process_cancellation.helpers.utils import Utils
from shopify_adapter.connector import ShopifyConnector
from pom_common.shopify import ShopManager

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

TENANT = os.environ.get('TENANT', 'frankandoak')
STAGE = os.environ.get('STAGE', 'x')
REGION = os.environ.get('REGION', 'us-east-1')

SQS_QUEUE = os.environ['SQS_QUEUE']
SHOPIFY_HANDLERS = {}


def handler(_, context):
    """
    Receives event payloads from an SQS queue. The payload is taken from the order
    event stream, detailed here:
        https://apidoc.newstore.io/newstore-cloud/hooks_eventstream.html
    Event Type: fulfillment_request.items_completed'
    """
    LOGGER.info('Beginning queue retrieval...')
    # Initiate newstore connection
    Utils.get_newstore_conn(context)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = sqs_consumer.consume(_process_cancellation, SQS_QUEUE)
    loop.run_until_complete(task)
    loop.stop()
    loop.close()


async def _process_cancellation(data: dict):
    """
    Args:
        message (dict): Raw cancellation event message

    Return empty dict if order does not exist in NewStore or originate from Shopify, effectively ignoring the event
    """
    response = {}

    newstore_order = _check_order_in_newstore(data['order'])
    if not newstore_order:
        LOGGER.exception('Message does not contain an order_id, no NewStore order can be found.')
    elif _is_shopify_historical_order(newstore_order):
        LOGGER.info('Message is a shopify historic order and will be ignored.')
    else:
        LOGGER.info(f'Received customer order from NewStore: {json.dumps(newstore_order)}')
        currency = newstore_order['totals']['currency']
        shopify_order_id = _get_shopify_order_id(newstore_order)
        if not shopify_order_id:
            return {'non_shopify_order': 'True'}

        LOGGER.info(f'Cancelling order {shopify_order_id}')
        response = get_shopify_handler(currency).cancel_order(shopify_order_id)
        LOGGER.info(f'Response from shopify: {response}')

    return response


def _check_order_in_newstore(message: dict) -> dict:
    """
    Args:
        message (dict): A NewStore cancellation event message from SQS

    Returns:
        A NewStore customer order (dict) for the provided cancellation event message, if it exists
    """
    if not message.get('id'):
        return {}

    order_id = message['id']
    customer_order = Utils.get_newstore_conn().get_external_order(order_id, id_type='id')
    return customer_order


def _get_shopify_order_id(newstore_order: dict) -> str:
    return _get_extended_attribute(newstore_order, 'order_id')


def _get_extended_attribute(newstore_order: dict, attribute_name: str) -> str:
    """
    Args:
        newstore_order (dict): NewStore customer_order object
        attribute_name (str): extended attribute name to retrieve

    Returns:
        Extended attribute value or None
    """
    if newstore_order.get('extended_attributes'):
        return next((attribute['value'] for attribute in newstore_order['extended_attributes']
                     if attribute['name'] == attribute_name), None)
    return None


def _is_shopify_historical_order(newstore_order: dict) -> bool:
    return newstore_order['channel'] == 'magento'


def get_shopify_handlers():
    global SHOPIFY_HANDLERS # pylint: disable=global-statement
    if len(SHOPIFY_HANDLERS) == 0:
        shop_manager = ShopManager(TENANT, STAGE, REGION)

        for shop_id in shop_manager.get_shop_ids():
            shopify_config = shop_manager.get_shop_config(shop_id)
            currency = shopify_config['currency']

            SHOPIFY_HANDLERS[currency] = ShopifyConnector(
                api_key=shopify_config['username'],
                password=shopify_config['password'],
                shop=shopify_config['shop']
            )

    return SHOPIFY_HANDLERS.values()


def get_shopify_handler(currency):
    if len(SHOPIFY_HANDLERS) == 0:
        get_shopify_handlers()

    return SHOPIFY_HANDLERS[currency]
