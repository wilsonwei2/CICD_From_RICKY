# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.

# Runs startup processes (expecting to be 'unused')
import netsuite.netsuite_environment_loader # pylint: disable=W0611
import netsuite.api.sale as nsas
from netsuite.service import (
    CustomFieldList,
    StringCustomFieldRef
)
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

    distribution_centres = Utils.get_distribution_centres()

    ns_order = get_external_order(fulfillment_request['order_id'])
    if ns_order['channel'] == 'magento':
        LOGGER.info('Skipping Historical Order')
        return True

    external_order_id = ns_order['external_order_id']
    LOGGER.info(f'External order id is {external_order_id}')

    # Get the Netsuite Sales Order
    sales_order = await get_sales_order(external_order_id)

    # Mark a virtual gift card as shipped regardless of its order presence
    # in NetSuite
    await ship_virtual_gift_cards(fulfillment_request)

    if sales_order:
        # Update the fulfillment locations for each item of the fulfillment request
        update_sales_order(sales_order, fulfillment_request)

        # Do not acknowledge using the API for ship from store
        fulfillment_location_id = fulfillment_request.get('fulfillment_location_id')
        if not fulfillment_location_id in distribution_centres:
            LOGGER.info('Fulfillment request is for a store, no acknowledgement is send.')
            return True

        # Acknowledge the fulfillment request since it was send to Netsuite
        if not NEWSTORE_HANDLER.send_acknowledgement(fulfillment_request['id']):
            LOGGER.critical('Fulfillment request was not acknowledged.')
            return

        LOGGER.info('Fulfillment request acknowledged.')

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

    item_ids_in_fulfillment = [item['id'] for item in fulfillment_request['items']]

    # It could be that the items ids in NewStore don't match anymore the item ids stored in Netsuite
    # Especially, for the DC rejections and fulfillments this might be the case
    # This needs to be checked first
    item_ids_in_fulfillment, updated_item_ids = check_item_ids_matching(sales_order, item_ids_in_fulfillment)

    update_items = []
    ship_method_id = service_level.get(shipping_service_level)

    product_mapping = Utils.get_product_mapping()

    if shipping_service_level in service_level:
        for item in sales_order_update.itemList.item:
            # To ensure that only the product IDs present in the fulfillment have their locations updated
            item_name = get_item_name(item, product_ids_in_fulfillment, product_mapping)
            item_id = get_item_id(item)

            # the sales order injection stores the UUID of each item in Netsuite
            # the check below ensures that the correct item is updated in Netsuite in case of
            # multiple of the same SKUs ordered but fulfilled in different locations
            # Fallback to the original logic if the item_id is not stored or not found
            if item_id is not None and item_id not in item_ids_in_fulfillment:
                LOGGER.info(f'Skip update of line {item_id}, {item_name} in Netsuite since it is not part of the fulfillment.')
                continue

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

    if len(updated_item_ids) > 0:
        LOGGER.info('Update Sales Order with swapped item ids...')
        update_sales_order_item_ids(updated_item_ids, updated_sales_order)

    LOGGER.info(f'Sales order successfully updated. Current status: {updated_sales_order.status}')

# Updates the sales order (again) and re-assigns the item ids to make sure the reference
# to NewStore items ids is still correct
def update_sales_order_item_ids(updated_item_ids, sales_order):
    sales_order_update = nsas.SalesOrder(
        internalId=sales_order.internalId,
        itemList=sales_order.itemList
    )

    update_items = []
    for item in sales_order_update.itemList.item:
        item_id = get_item_id(item)
        for mapping in updated_item_ids:
            if mapping['old_item_id'] == item_id:
                LOGGER.info(f'Update SalesOrderItem and swap {mapping["old_item_id"]} with {mapping["new_item_id"]}')

                sales_order_item = nsas.SalesOrderItem(
                    item=item.item,
                    line=item.line
                )
                item_custom_field_list = []
                item_custom_field_list.append(
                    StringCustomFieldRef(
                        scriptId='custcol_nws_item_id',
                        value=mapping['new_item_id']
                    )
                )
                sales_order_item['customFieldList'] = CustomFieldList(item_custom_field_list)
                update_items.append(sales_order_item)

    sales_order_update.itemList.item = update_items
    sales_order_update.itemList.replaceAll = False

    LOGGER.info(f"SalesOrder to update: \n{json.dumps(serialize_object(sales_order_update), indent=4, default=Utils.json_serial)}")
    result, updated_sales_order = nsas.update_sales_order(sales_order_update)

    if not result:
        raise Exception(f'Failed to update sales order: {updated_sales_order}')

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


# Gets the NewStore Item ID stored by the Sales Order injection script from the item
def get_item_id(item):
    if item['customFieldList'] is not None:
        custom_field_list = item['customFieldList']['customField']
        for custom_field in custom_field_list:
            script_id = custom_field['scriptId']
            if script_id == 'custcol_nws_item_id':
                return str(custom_field['value'])

    return None


# Gets the rejected flag stored for a Sales Order Item
def get_nws_rejected_flag(item):
    if item['customFieldList'] is not None:
        custom_field_list = item['customFieldList']['customField']
        for custom_field in custom_field_list:
            script_id = custom_field['scriptId']
            if script_id == 'custcol_nws_fulfillrejected':
                return custom_field['value']

    return False


def check_item_ids_matching(sales_order, item_ids_in_fulfillment):
    # 1) Get all sales order items which should be updated
    sales_order_items = []
    updated_item_ids = []
    already_processed_rejected_ids = []
    for item in sales_order.itemList.item:
        item_id = get_item_id(item)

        if item_id in item_ids_in_fulfillment:
            sales_order_items.append(item)

    # 2) If there is no item found, proceed with the data as given
    if len(sales_order_items) == 0:
        LOGGER.info('No Sales Order Item matches the given ID list.')
        return item_ids_in_fulfillment, updated_item_ids

    # 3) Check if one of the sales order items is already fulfilled and matches the list
    #    of ids in the NewStore fulfillment request, then we need to swap
    for item in sales_order_items: # pylint: disable=too-many-nested-blocks
        item_is_fulfilled = item.itemIsFulfilled or \
            (item.quantityFulfilled is not None and item.quantityFulfilled > 0)
        if item_is_fulfilled:
            item_id = get_item_id(item)

            LOGGER.info(f'The item {item_id}, line {item.line}, is already fulfilled.')
            LOGGER.info(f'Try to find a rejected item and replace the IDs.')

            rejected_items = get_rejected_items(sales_order, item)

            if len(rejected_items) == 0:
                LOGGER.info('Rejected item not found. Will proceed with original data')

            for rejected_item in rejected_items:
                rejected_item_id = get_item_id(rejected_item)

                if rejected_item_id in already_processed_rejected_ids:
                    LOGGER.info(f'ID {rejected_item_id} already processed.')
                    continue

                LOGGER.info(f'Replace {item_id} with {rejected_item_id}')
                item_ids_in_fulfillment.remove(item_id)
                item_ids_in_fulfillment.append(rejected_item_id)

                # Add to already processed list
                already_processed_rejected_ids.append(rejected_item_id)

                # Item IDs have been swapped
                updated_item_ids.append({
                    'old_item_id': item_id,
                    'new_item_id': rejected_item_id
                })
                updated_item_ids.append({
                    'old_item_id': rejected_item_id,
                    'new_item_id': item_id
                })

    return item_ids_in_fulfillment, updated_item_ids

# Gets the rejected items which have the same SKU as the given item.
def get_rejected_items(sales_order, fulfilled_item):
    product_id = fulfilled_item.item.name
    rejected_items = []
    for item in sales_order.itemList.item:
        if product_id == item.item.name:
            rejected = get_nws_rejected_flag(item)
            if rejected:
                rejected_items.append(item)

    return rejected_items
