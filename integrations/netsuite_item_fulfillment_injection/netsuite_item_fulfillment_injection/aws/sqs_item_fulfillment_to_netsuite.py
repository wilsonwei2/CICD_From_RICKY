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

PHYSICAL_GC_ID = os.environ.get('PHYSICAL_GC_ID', 'PGC')
PHYSICAL_GC_SKU = os.environ.get('PHYSICAL_GC_SKU', '5500000-000')

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
    payload = get_fulfillment_request(message.get('payload'))
    fulfillment_request = replace_pgc_product_id(payload, PHYSICAL_GC_ID, PHYSICAL_GC_SKU)
    order_id = fulfillment_request['orderId']

    # The customer_order endpoint is defined in the `affiliate app` end points
    customer_order_envelope = Utils.get_newstore_conn().get_customer_order(order_id)
    if not customer_order_envelope:
        raise Exception(f'Customer order for order id {order_id} not found on NewStore')
    LOGGER.info(f'customer_order_envelope: \n{json.dumps(customer_order_envelope, indent=4)}')

    customer_order = customer_order_envelope['customer_order']

    if customer_order['channel'] == 'magento':
        LOGGER.info('Skip fulfillment request because of a Historical Order')
        return True

    order_external_id = customer_order['sales_order_external_id']
    fulfillment_location_id = fulfillment_request.get('fulfillmentLocationId')
    if not Utils.is_store(fulfillment_location_id):
        LOGGER.info(f'Fulfillment request for order {order_external_id} has a DC fulfillment location and will be handled in the '
                    f'sales order lambda. Ignoring message.')
        return True

    sales_order = await get_sales_order(order_external_id)

    # Before creating the ItemFulfillment, update SalesOrder with correct location in item level
    fulfillment_request = update_sales_order(sales_order, fulfillment_request)
    if fulfillment_request:
        LOGGER.info(f"Updated fulfillment request: {json.dumps(serialize_object(fulfillment_request), indent=4, default=Utils.json_serial)}")

        response = create_item_fulfillment(fulfillment_request, sales_order)
        if response:
            LOGGER.info('ItemFulfillment created successfully.')

        return response
    LOGGER.info('Item fulfillment is not needed.')


def create_item_fulfillment(fulfillment_request, sales_order):
    item_fulfillment = nsas.initialize_record('itemFulfillment', 'salesOrder', sales_order.internalId)
    if not item_fulfillment:
        raise Exception('Not able to initialize item fulfillment.')
    item_fulfillment, item_fulfillment_items = pf.parse_info(fulfillment_request, sales_order, item_fulfillment)

    LOGGER.info(f"Item Fulfillment transformed: \n{json.dumps(serialize_object(item_fulfillment), indent=4, default=Utils.json_serial)}")
    LOGGER.info(f"Item Fulfillment Items transformed: \n{json.dumps(serialize_object(item_fulfillment_items), indent=4, default=Utils.json_serial)}")

    check_product_internal_ids(item_fulfillment_items)
    mark_shipped_items(item_fulfillment_items, item_fulfillment)

    LOGGER.info(f"ItemFulfillment: \n{json.dumps(serialize_object(item_fulfillment), indent=4, default=Utils.json_serial)}")
    return bool(nsas.create_item_fulfillment(item_fulfillment))


def update_sales_order(sales_order, fulfillment_request):
    fulfillment_rejected_script_id = os.environ.get('netsuite_fulfillment_rejected_flag_script_id',
                                                    'custcol_nws_fulfillrejected')
    sales_order_update = nsas.SalesOrder(
        internalId=sales_order.internalId,
        itemList=sales_order.itemList
    )
    product_ids_in_fulfillment = [item['node']['productId'] for item in fulfillment_request['items']['edges']]
    item_ids_in_fulfillment = [item['node']['id'] for item in fulfillment_request['items']['edges']]
    netsuite_location_id = Utils.get_netsuite_store_internal_id(fulfillment_request['fulfillmentLocationId'])
    update_items = []

    for item in sales_order_update.itemList.item:
        if len(item.item.name.split(' ')) < 3:
            continue

        is_rejected = False
        for custcol in item.customFieldList.customField:
            if custcol.scriptId == fulfillment_rejected_script_id:
                is_rejected = custcol.value

        item_is_fulfilled = item.itemIsFulfilled or \
            (item.quantityFulfilled is not None and item.quantityFulfilled > 0)

        location = item.location

        item_name = item.item.name.split(' ')[2]
        item_id = get_item_id(item)

        # Remove fields we don't need for line reference so they are not
        # updated to identical values (also avoids permissions errors)
        item = nsas.SalesOrderItem(
            item=item.item,
            line=item.line
        )

        LOGGER.info(f'Item {item_name}, {item_id} is fulfilled {item_is_fulfilled}, is rejected {is_rejected}')

        # the sales order injection stores the UUID of each item in Netsuite
        # the check below ensures that the correct item is updated in Netsuite in case of
        # multiple of the same SKUs ordered but fulfilled in different locations
        # Fallback to the original logic if the item_id is not stored or not found
        if item_id is not None and item_id not in item_ids_in_fulfillment:
            LOGGER.info(f'Skip update of line {item_id}, {item_name} in Netsuite since it is not part of the fulfillment.')
            continue

        LOGGER.info(f"Verify if product {item_name} is in {product_ids_in_fulfillment}")

        if (item_id is not None and item_id in item_ids_in_fulfillment) or (item_name in product_ids_in_fulfillment) \
                and not item_is_fulfilled \
                and not is_rejected:

            if item_name not in Utils.get_virtual_product_ids_config():
                # We can only set commitInventory on inventory items and avoid doing so in non-inventory items
                item.commitInventory = '_availableQty'

            if location is None:
                item.location = nsas.RecordRef(internalId=netsuite_location_id)

            item_ids_in_fulfillment.remove(item_id)

            update_items.append(item)

    remove_fulfilled_items(item_ids_in_fulfillment, fulfillment_request)

    if len(update_items) > 0:
        sales_order_update.itemList.item = update_items
        sales_order_update.itemList.replaceAll = False

        LOGGER.info(f"SalesOrder to update: \n{json.dumps(serialize_object(sales_order_update), indent=4, default=Utils.json_serial)}")
        result, updated_sales_order = nsas.update_sales_order(sales_order_update)

        if not result:
            raise Exception(f'Failed to update sales order: {updated_sales_order}')

        LOGGER.info(f'Sales order successfully updated. Current status: {updated_sales_order.status}')
        return fulfillment_request
    LOGGER.info(f'All the items in the fulfillment request are fulfilled. Ignoring message')
    return False


async def get_sales_order(order_id):
    sales_order = nsas.get_sales_order(order_id)
    if not sales_order:
        raise Exception('SalesOrder not found on NetSuite for order %s.' % (order_id))
    return sales_order


def remove_fulfilled_items(item_list, fulfillment_request):
    for idx, node in enumerate(fulfillment_request['items']['edges']):
        if node['node']['productId'] in item_list:
            removed_item = fulfillment_request['items']['edges'].pop(idx)
            LOGGER.info(f"fulfilled item removed from payload: {removed_item}")


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


# Gets the NewStore Item ID stored by the Sales Order injection script from the item
def get_item_id(item):
    custom_field_list = item['customFieldList']['customField']
    for custom_field in custom_field_list:
        script_id = custom_field['scriptId']
        if script_id == 'custcol_nws_item_id':
            return str(custom_field['value'])

    return None


def replace_pgc_product_id(fulfillment_request_event, physical_gc_id, physical_gc_sku):
    for item in fulfillment_request_event['items']['edges']:
        item['node']['productId'] = item['node']['productId'] if item['node']['productId'] != physical_gc_id else physical_gc_sku
    return fulfillment_request_event


def get_fulfillment_request(fulfillment_payload):
    fulfillment_id = fulfillment_payload["id"]

    graphql_query = """query MyQuery($id: String!, $tenant: String!) {
        fulfillmentRequest(id: $id, tenant: $tenant) {
            fulfillmentLocationId       
            id          
            items { 
                edges {
                    node {
                            id        
                            carrier        
                            productId        
                            trackingCode        
                            shippedAt 
                        }
                    }
                }           
            associateId              
            serviceLevel              
            orderId              
            logicalTimestamp 
        }
    }"""
    data = {
        "query": graphql_query,
        "variables": {
            "id": fulfillment_id,
            "tenant": os.environ.get('TENANT_TEMP')
        }
    }

    graphql_response = Utils.get_newstore_conn().graphql_api_call(data)
    return graphql_response['data']['fulfillmentRequest']
