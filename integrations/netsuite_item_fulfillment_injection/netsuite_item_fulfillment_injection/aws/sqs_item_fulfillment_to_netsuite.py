# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.

# Runs startup processes (expecting to be 'unused')
import netsuite.netsuite_environment_loader # pylint: disable=W0611
import netsuite.api.sale as nsas
from netsuite.api.item import get_product_by_name
import logging
import os
import json
import asyncio
import netsuite_item_fulfillment_injection.helpers.sqs_consumer as sqs_consumer
import netsuite_item_fulfillment_injection.transformers.process_fulfillment as pf
from netsuite_item_fulfillment_injection.helpers.utils import Utils
from zeep.helpers import serialize_object

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
SQS_QUEUE = os.environ['SQS_QUEUE']


def handler(_, context):
    """
    Receives event payloads from an SQS queue. The payload is taken from the order
    event stream, detailed here:
        https://apidoc.newstore.io/newstore-cloud/hooks_eventstream.html
    Event Type: fulfillment_request.items_completed'
    """
    LOGGER.info(f'Beginning queue retrieval...')
    # Initialize newstore conector
    Utils.get_newstore_conn(context)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = sqs_consumer.consume(process_fulfillment, SQS_QUEUE)
    loop.run_until_complete(task)
    loop.stop()
    loop.close()


async def process_fulfillment(message):
    LOGGER.info(f"Message to process: \n {json.dumps(message, indent=4)}")
    fulfillment_request = message.get('payload')
    order_id = fulfillment_request['order_id']

    # The customer_order endpoint is defined in the `affiliate app` end points
    customer_order_envelope = Utils.get_newstore_conn().get_customer_order(order_id)
    if not customer_order_envelope:
        raise Exception(f'Customer order for order id {order_id} not found on NewStore')
    LOGGER.info(f'customer_order_envelope: \n{json.dumps(customer_order_envelope, indent=4)}')

    customer_order = customer_order_envelope['customer_order']

    order_external_id = customer_order['sales_order_external_id']
    if order_external_id.startswith('HIST-'):
        LOGGER.info('Skip fulfillment request because is a Historical Order')
        return True

    fulfillment_location_id = fulfillment_request.get('fulfillment_location_id')
    if not Utils.is_store(fulfillment_location_id):
        LOGGER.info(f'Fulfillment request for order {order_external_id} has a DC fulfillment location and will be handled in the '
                    f'sales order lambda. Ignoring message.')
        return True

    fulfillment_request_id = fulfillment_request['id']
    if await check_existing_item_fulfillment(fulfillment_request_id):
        LOGGER.info(f'Fulfillment request {fulfillment_request_id} for order {order_external_id} already has an ' \
                    'ItemFulfillment on NetSuite. Ignoring message.')
        return True

    sales_order = await get_sales_order(order_external_id)

    # Before creating the ItemFulfillment, update SalesOrder with correct location in item level
    update_sales_order(sales_order, fulfillment_request)

    response = create_item_fulfillment(fulfillment_request, sales_order)
    if response:
        LOGGER.info('ItemFulfillment created successfully.')

    return response


def create_item_fulfillment(fulfillment_request, sales_order):
    item_fulfillment = nsas.initialize_record('itemFulfillment', 'salesOrder', sales_order.internalId)
    if not item_fulfillment:
        raise Exception('Not able to initialize item fulfillment.')
    item_fulfillment, item_fulfillment_items = pf.parse_info(fulfillment_request, sales_order, item_fulfillment)

    LOGGER.info(f"Item Fulfillment transformed: \n{json.dumps(serialize_object(item_fulfillment), indent=4, default=Utils.json_serial)}")
    LOGGER.info(f"Item Fulfillment Items transformed: \n{json.dumps(serialize_object(item_fulfillment_items), indent=4, default=Utils.json_serial)}")

    check_product_internal_ids(item_fulfillment_items)
    mark_shipped_items(item_fulfillment_items, item_fulfillment)

    # Remove read-only fields
    for item in item_fulfillment['itemList']['item']:
        if not item['customFieldList'] or not item['customFieldList']['customField']:
            continue

        for custom_field in item['customFieldList']['customField']:
            if custom_field['scriptId'] == 'custcol_ab_rateonif':
                item['customFieldList']['customField'].remove(custom_field)

    LOGGER.info(f"ItemFulfillment: \n{json.dumps(serialize_object(item_fulfillment), indent=4, default=Utils.json_serial)}")
    return bool(nsas.create_item_fulfillment(item_fulfillment))


def update_sales_order(sales_order, fulfillment_request):
    fulfillment_rejected_script_id = os.environ.get('netsuite_fulfillment_rejected_flag_script_id',
                                                    'custcol_ab_fulfillmentrejected')
    sales_order_update = nsas.SalesOrder(
        internalId=sales_order.internalId,
        itemList=sales_order.itemList
    )
    product_ids_in_fulfillment = [item['product_id'] for item in fulfillment_request['items']]
    netsuite_location_id = Utils.get_netsuite_store_internal_id(fulfillment_request['fulfillment_location_id'])
    update_items = []

    for item in sales_order_update.itemList.item:
        if len(item.item.name.split(' ')) < 3:
            continue

        is_rejected = False
        for custcol in item.customFieldList.customField:
            if custcol.scriptId == fulfillment_rejected_script_id:
                is_rejected = custcol.value

        item_is_fulfilled = item.itemIsFulfilled

        # Remove fields we don't need for line reference so they are not
        # updated to identical values (also avoids permissions errors)
        item = nsas.SalesOrderItem(
            item=item.item,
            line=item.line
        )

        LOGGER.info(f"Verify if product {item.item.name.split(' ')[2]} is in {product_ids_in_fulfillment}")

        if item.item.name.split(' ')[2] in product_ids_in_fulfillment \
                and not item_is_fulfilled \
                and not is_rejected \
                and item.location is None:

            if item.item.name.split(' ')[2] not in Utils.get_virtual_product_ids_config():
                # We can only set commitInventory on inventory items and avoid doing so in non-inventory items
                item.commitInventory = '_availableQty'

            item.location = nsas.RecordRef(internalId=netsuite_location_id)
            product_ids_in_fulfillment.remove(item.item.name.split(' ')[2])

        update_items.append(item)

    sales_order_update.itemList.item = update_items
    sales_order_update.itemList.replaceAll = False

    LOGGER.info(f"SalesOrder to update: \n{json.dumps(serialize_object(sales_order_update), indent=4, default=Utils.json_serial)}")
    result, updated_sales_order = nsas.update_sales_order(sales_order_update)

    if not result:
        raise Exception(f'Failed to update sales order: {updated_sales_order}')

    LOGGER.info(f'Sales order successfully updated. Current status: {updated_sales_order.status}')

async def get_sales_order(order_id):
    sales_order = nsas.get_sales_order(order_id)
    if not sales_order:
        raise Exception('SalesOrder not found on NetSuite for order %s.' % (order_id))
    return sales_order


async def check_existing_item_fulfillment(external_id):
    item_fulfillment = nsas.get_transaction(external_id, '_itemFulfillment')
    if item_fulfillment:
        return True
    return False


def mark_shipped_items(item_fulfillment_items, item_fulfillment):
    # We can have the same item routed to diferent locations, so an array is necessary to not have keys being overwritten
    items = [{str(item['item']['internalId']):{'location': item['location']}} for item in item_fulfillment_items]
    items_to_fulfill = [str(item['item']['internalId']) for item in item_fulfillment_items for x in range(item['quantity'])]
    LOGGER.debug(f"mark_shipped_items item_fulfillment: {json.dumps(serialize_object(item_fulfillment), indent=4, default=Utils.json_serial)}")
    LOGGER.debug("mark_shipped_items item_fulfillment_items: " \
                 f"{json.dumps(serialize_object(item_fulfillment_items), indent=4, default=Utils.json_serial)}")
    LOGGER.debug(f"mark_shipped_items items: {json.dumps(serialize_object(items), indent=4, default=Utils.json_serial)}")
    LOGGER.debug(f"mark_shipped_items items_to_fulfill: {json.dumps(serialize_object(items_to_fulfill), indent=4, default=Utils.json_serial)}")

    for item in item_fulfillment['itemList']['item']:
        item['itemReceive'] = False
        item['quantity'] = 0

        if not items_to_fulfill or not item['location']:
            continue

        for fulfilled_item in items:
            if str(item['item']['internalId']) in items_to_fulfill \
                    and str(item['item']['internalId']) in fulfilled_item \
                    and int(item['location']['internalId']) == int(fulfilled_item[item['item']['internalId']]['location']['internalId']):
                item['itemReceive'] = True
                item['quantity'] = 1
                items_to_fulfill.remove(str(item['item']['internalId']))
                break


def check_product_internal_ids(item_fulfillment_items):
    for item in item_fulfillment_items:
        product = get_product_by_name(item['item']['internalId'])
        assert product, f"Could not find product {item['item']['internalId']} in NetSuite."
        item['item']['internalId'] = product['internalId']
