# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.
import os
import json
import asyncio
import netsuite.netsuite_environment_loader  # pylint: disable=W0611
import netsuite.api.sale as ns_s
from zeep.helpers import serialize_object
import netsuite_cancellation_injection.helpers.sqs_consumer as sqs_consumer
from netsuite_cancellation_injection.helpers.utils import LOGGER
from netsuite_cancellation_injection.helpers.utils import Utils

SQS_QUEUE = os.environ.get('SQS_QUEUE')

# Runs startup processes
os.environ['TENANT_NAME'] = os.environ.get('TENANT', 'frankandoak')
os.environ['NEWSTORE_STAGE'] = os.environ.get('STAGE', 's')


def handler(_event, context):
    LOGGER.info(f'Beginning queue retrieval...')
    # Initialize newstore conector
    Utils.get_newstore_conn(context)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = sqs_consumer.consume(process_cancellation, SQS_QUEUE)
    loop.run_until_complete(task)
    loop.stop()
    loop.close()


async def process_cancellation(message):
    LOGGER.info(f"Message to process: \n {json.dumps(message, indent=4)}")
    event_cancellation = message['payload']
    order_id = event_cancellation['id']
    sales_order = get_sales_order(order_id)

    if message['event_type'] == 'order.cancelled':
        return await handle_order_cancellation(sales_order)

    if message['event_type'] == 'order.items_cancelled':
        return await handle_item_cancellation(event_cancellation, sales_order)

    LOGGER.warning(f"Event of type {message['event_type']} cannot be handled in this integration, ignoring event...")
    return True


async def handle_order_cancellation(sales_order):
    """
    Full Cancellation (original event order.cancelled):
    1. Get the Netsuite Sales Order
    2. Go through the items, set them all to closed: True
    3. Update the Sales order
    Note: No need to check for items, they all need to be closed - that’s it
    """
    sales_order_update = ns_s.SalesOrder(
        internalId=sales_order['internalId']
    )
    update_items = []

    for item in sales_order['itemList']['item']:
        # Remove fields we don't need for line reference so they are not
        # updated to identical values (also avoids permissions errors)
        update_items.append(
            ns_s.SalesOrderItem(
                item=item['item'],
                line=item['line'],
                isClosed=True
            )
        )

    sales_order_update['itemList'] = {
        'item': update_items,
        'replaceAll': True
    }

    return update_sales_order(sales_order_update)


async def handle_item_cancellation(event_cancellation, sales_order):
    """
    Item Cancellation (original event order.items_cancelled):
    1. Get the Netsuite Sales Order
    2. Go through the items, set the items which are cancelled in Newstore to closed
        2.1. If there is a discount related for the item, there is a discount item in Netsuite (as next line) → this needs to be closed as well
    3. Recalculate the Payment Item Total
        3.1. Edge Case: Multiple Payment items - to be checked
    """
    sales_order_update = ns_s.SalesOrder(
        internalId=sales_order['internalId']
    )
    cancelled_product_ids = [str(item['product_id']) for item in event_cancellation['items']]
    cancelled_item_ids = [item['id'] for item in event_cancellation['items']]
    has_discount = False
    amount_cancelled = 0.0
    update_items = []

    for item in sales_order['itemList']['item']:
        if item['itemIsFulfilled'] or item['isClosed'] or \
            (item['quantityFulfilled'] is not None and item['quantityFulfilled'] > 0):
            continue

        # Remove fields we don't need for line reference so they are not
        # updated to identical values (also avoids permissions errors)
        updated_item = ns_s.SalesOrderItem(
            item=item['item'],
            line=item['line'],
            amount=0.0,
            isClosed=True
        )

        item_id = get_item_id(item)
        product_id = get_product_id_by_netsuite_name(item, cancelled_product_ids)

        # the sales order injection stores the UUID of each item in Netsuite
        # the check below ensures that the correct item is updated in Netsuite in case of
        # multiple of the same SKUs ordered
        # Fallback to the original logic if the item_id is not stored or not found
        if item_id is not None and item_id not in cancelled_item_ids:
            LOGGER.info(f'Skip update of line {item_id}, {product_id} in Netsuite since it is not part of the cancellation.')
            continue

        if product_id in cancelled_product_ids:
            updated_item['quantity'] = 0
            update_items.append(updated_item)
            cancelled_product_ids.remove(product_id)
            LOGGER.info(f'DEBUG MSG display item dict: {item}')
            amount_cancelled += abs(float(item['amount']))
            taxes = get_item_taxes(item)

            if item_has_discount(item):
                has_discount = True

            if taxes:
                amount_cancelled += (float(item['amount']) * taxes) / 100

        elif has_discount and str(item['item']['internalId']) == str(Utils.get_netsuite_config()['newstore_discount_item_id']):
            updated_item['rate'] = 0.0
            update_items.append(updated_item)
            amount_cancelled -= abs(float(item['amount']))
            has_discount = False

        elif is_payment_item(item) and amount_cancelled > 0:
            if abs(item['amount']) >= amount_cancelled:
                updated_item['amount'] = -abs(abs(item['amount']) - amount_cancelled)
                amount_cancelled = 0.0
            else:
                amount_cancelled -= abs(item['amount'])
                updated_item['amount'] = 0.0

            updated_item['isClosed'] = False
            update_items.append(updated_item)

        elif is_tax_rounding_adj_item(item):
            if item['amount'] < 0:
                updated_item['amount'] = 0.0
                updated_item['isClosed'] = False
                update_items.append(updated_item)

    sales_order_update['itemList'] = {
        'item': update_items,
        'replaceAll': False
    }

    return update_sales_order(sales_order_update)


def get_sales_order(order_id):
    customer_order = get_customer_order(order_id)
    LOGGER.info('Getting SalesOrder from NetSuite.')
    sales_order = ns_s.get_sales_order(customer_order['sales_order_external_id'])
    assert sales_order, "Couldn't get SalesOrder from NetSuite."
    return sales_order


def update_sales_order(sales_order):
    LOGGER.info(f"SalesOrder to update: \n{json.dumps(serialize_object(sales_order), indent=4, default=Utils.json_serial)}")
    result, updated_sales_order = ns_s.update_sales_order(sales_order)

    if not result:
        raise Exception(f'Failed to update sales order: {updated_sales_order}')

    LOGGER.info(f'Sales order successfully updated. Current status: {updated_sales_order.status}')
    return True


def item_has_discount(item):
    for custom_field in item['customFieldList']['customField']:
        if custom_field['scriptId'] in ('custcol_fao_line_item_discount', 'custcol_fao_order_item_discount') \
                and float(custom_field['value']) > 0:
            return True
    return False


def is_payment_item(item):
    return int(item['item']['internalId']) in Utils.get_payment_ids()


def is_tax_rounding_adj_item(item):
    return int(item['item']['internalId']) == Utils.get_tax_rounding_adj_id()

def get_customer_order(order_id):
    LOGGER.info('Getting customer order from NewStore.')
    customer_order = Utils.get_newstore_conn().get_customer_order(order_id)
    assert customer_order, "Couldn't get customer_order from Newstore."
    LOGGER.info(f"Customer order from NewStore\n {json.dumps(customer_order.get('customer_order', {}))}")
    return customer_order.get('customer_order', {})


def get_product_id_by_netsuite_name(item, cancelled_product_ids):
    netsuite_name = item['item']['name']
    product_id = None
    for possible_product_id in netsuite_name.split(' '):
        if possible_product_id in cancelled_product_ids:
            product_id = possible_product_id
            break
    return product_id


def get_item_taxes(item):
    for custom_field in item['customFieldList']['customField']:
        if custom_field['scriptId'] == 'custcol_nws_override_taxcode':
            return float(custom_field['value'])
    return 0


# Gets the NewStore Item ID stored by the Sales Order injection script from the item
def get_item_id(item):
    if item['customFieldList'] is not None:
        custom_field_list = item['customFieldList']['customField']
        for custom_field in custom_field_list:
            script_id = custom_field['scriptId']
            if script_id == 'custcol_nws_item_id':
                return str(custom_field['value'])

    return None
