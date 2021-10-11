# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.

# Runs startup processes (expecting to be 'unused')
import netsuite.netsuite_environment_loader # pylint: disable=W0611
import netsuite.api.sale as nsas
import logging
import os
import json
import asyncio
import netsuite_fulfillment_assignment.helpers.sqs_consumer as sqs_consumer

from datetime import datetime
from netsuite_fulfillment_assignment.helpers.utils import Utils
from zeep.helpers import serialize_object

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
SQS_QUEUE = os.environ['SQS_QUEUE']
SQS_QUEUE_DLQ = os.environ['SQS_QUEUE_DLQ']
NEWSTORE_HANDLER = None

def handler(_event, _context):
    """
    Receives event payloads from an SQS queue. The payload is taken from the order
    event stream, detailed here:
        https://apidoc.newstore.io/newstore-cloud/hooks_eventstream.html
    Event Type: fulfillment_request.assigned'
    """
    LOGGER.info(f'Beginning queue retrieval...')

    global NEWSTORE_HANDLER # pylint: disable=W0603

    NEWSTORE_HANDLER = Utils.get_ns_handler(_context)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = sqs_consumer.consume(process_fulfillment_assignment, _get_sqs_queue())
    loop.run_until_complete(task)
    loop.stop()
    loop.close()


async def process_fulfillment_assignment(message):
    LOGGER.info(f"Message to process: \n {json.dumps(message, indent=4)}")

    fulfillment_request = message.get("payload")

    if 'service_level' in fulfillment_request and fulfillment_request['service_level'] == 'IN_STORE_HANDOVER':
        return True

    ns_order = get_external_order(fulfillment_request['order_id'])
    if ns_order['channel'] == 'magento':
        LOGGER.info('Skipping Historical Order')
        return True

    external_order_id = ns_order['external_order_id']
    LOGGER.info(f'External order id is {external_order_id}')

    # Get the Netsuite Sales Order
    sales_order = await get_sales_order(external_order_id)

    if sales_order:
        # Update the fulfillment locations for each item of the fulfillment request
        update_sales_order(sales_order, fulfillment_request)

        # Acknowledge the fulfillment request since it was send to Netsuite
        if not NEWSTORE_HANDLER.send_acknowledgement(fulfillment_request['id']):
            LOGGER.critical('Fulfillment request was not acknowledged.')
            return

        LOGGER.info('Fulfillment request acknowledged.')

        # Process virtual/electronic gift cards if needed
        await ship_virtual_gift_cards(fulfillment_request)

        return True

    return False

# Updates the fulfillment location for each item in NetSuite
def update_sales_order(sales_order, fulfillment_request):
    sales_order_update = nsas.SalesOrder(
        internalId=sales_order.internalId,
        itemList=sales_order.itemList
    )

    shipping_service_level = None
    if 'service_level' in fulfillment_request:
        shipping_service_level = fulfillment_request['service_level']

    service_level = Utils.get_netsuite_service_level()
    netsuite_location_id = Utils.get_netsuite_store_internal_id(fulfillment_request['fulfillment_location_id'])
    product_ids_in_fulfillment = [item['product_id'] for item in fulfillment_request['items']]

    update_items = []
    ship_method_id = service_level.get(shipping_service_level)

    product_mapping = Utils.get_product_mappping()

    if shipping_service_level in service_level:
        for item in sales_order_update.itemList.item:
            # To ensure that only the product IDs present in the fulfillment have their locations updated
            item_name = get_item_name(item, product_ids_in_fulfillment, product_mapping)
            if item_name in product_ids_in_fulfillment:
                # Remove fields we don't need for line reference so they are not
                # updated to identical values (also avoids permissions errors)
                item = nsas.SalesOrderItem(
                    item=item.item,
                    line=item.line
                )

                item.location = nsas.RecordRef(internalId=str(netsuite_location_id))
                item.shipMethod = nsas.RecordRef(internalId=str(ship_method_id))
                LOGGER.info(f'Current shipping level is {shipping_service_level} and its netsuite value is {ship_method_id}')

                update_items.append(item)
                product_ids_in_fulfillment.remove(item_name)

    sales_order_update.itemList.item = update_items
    sales_order_update.itemList.replaceAll = False
    sales_order_update.shipMethod = nsas.RecordRef(internalId=str(ship_method_id))

    LOGGER.info(f"SalesOrder to update: \n{json.dumps(serialize_object(sales_order_update), indent=4, default=Utils.json_serial)}")
    result, updated_sales_order = nsas.update_sales_order(sales_order_update)

    if not result:
        raise Exception(f'Failed to update sales order: {updated_sales_order}')

    LOGGER.info(f'Sales order successfully updated. Current status: {updated_sales_order.status}')


#
# Virtual or Electronic Gift Cards need to be set to shipped and paid immediately. This function
# checks if there are gift cards in the order, and generates a shipment if so.
#
async def ship_virtual_gift_cards(fulfillment_request):
    items_to_ship = []
    for line_item in fulfillment_request.get('items', []):
        if line_item['product_id'] == 'EGC':
            LOGGER.info(f'Item {line_item} is a virtual gift card.')
            items_to_ship.append(line_item)
    if not items_to_ship:
        return items_to_ship

    LOGGER.info('Fulfillment request contains virtual gift cards - set them to shipped.')
    shipment_json = {
        'line_items': [
            {
                'product_ids': [item['product_id'] for item in items_to_ship],
                'shipment': {
                    'tracking_code': 'N/A',
                    'carrier': 'N/A'
                }
            }
        ]
    }

    if not NEWSTORE_HANDLER.send_shipment(fulfillment_request['id'], shipment_json):
        raise Exception('Fulfillment request was not informed of shipping for virtual gift cards.')
    LOGGER.info('Fulfillment request informed of shipping for virtual gift cards.')
    return items_to_ship


# Get the sales order from NetSuite
async def get_sales_order(order_id):
    sales_order = nsas.get_sales_order(order_id)
    if not sales_order:
        LOGGER.error(f'SalesOrder not found on NetSuite for order {order_id}.')
    return sales_order


def _get_sqs_queue():
    if _run_dead_letter():
        sqs_queue = SQS_QUEUE_DLQ
    else:
        sqs_queue = SQS_QUEUE

    return sqs_queue


def _run_dead_letter():
    hours = [int(hour.strip()) for hour in os.environ['RUN_DLQ_AT'].split(',')]
    minutes = int(os.environ['RUN_DLQ_FOR'])
    for hour in hours:
        time_to_run = (hour * 60) + minutes
        time_now = (datetime.now().hour * 60) + datetime.now().minute
        LOGGER.info(f'Hour: {hour}; Minutes: {minutes}; Time to run: {time_to_run}; Time now: {time_now}')
        if datetime.now().hour >= hour and time_to_run > time_now:
            return True
    return False


def get_external_order(uuid):
    return NEWSTORE_HANDLER.get_external_order(uuid, id_type='id')


def get_item_name(item, product_ids_in_fulfillment, product_mapping):
    item_name = item.item.name
    for possible_item_id in item.item.name.split(' '):

        if possible_item_id in product_mapping:
            possible_item_id = product_mapping[possible_item_id]

        if possible_item_id in product_ids_in_fulfillment:
            item_name = possible_item_id
            break

    return item_name
