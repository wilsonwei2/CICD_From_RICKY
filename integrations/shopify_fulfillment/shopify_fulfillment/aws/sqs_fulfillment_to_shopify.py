# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.
import logging
import os
import json
import asyncio
import shopify_fulfillment.helpers.sqs_consumer as sqs_consumer
from shopify_fulfillment.helpers.utils import Utils
from shopify_adapter.connector import ShopifyConnector
from pom_common.shopify import ShopManager

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

TENANT = os.environ.get('TENANT', 'frankandoak')
STAGE = os.environ.get('STAGE', 'x')
REGION = os.environ.get('REGION', 'us-east-1')

SQS_QUEUE = os.environ['SQS_QUEUE']
SHOPIFY_HANDLERS = {}
DC_LOCATION_ID_MAP = Utils.get_shopify_dc_location_id_map()


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
    task = sqs_consumer.consume(process_fulfillment, SQS_QUEUE)
    loop.run_until_complete(task)
    loop.stop()
    loop.close()


async def process_fulfillment(message):
    LOGGER.info(f"Message to process: \n {json.dumps(message, indent=4)}")
    fulfillment_event = message.get('order')
    order_id = fulfillment_event['order_id']

    customer_order = Utils.get_newstore_conn().get_customer_order(order_id).get('customer_order', {})
    if not customer_order:
        raise Exception("Couldn't retrieve customer order on NewStore")

    is_endless_aisle = Utils.is_endless_aisle(customer_order)
    not_a_web_order = customer_order.get('channel_type') != 'web'
    is_historic_order = Utils.is_historic_order({"order": customer_order})
    if is_endless_aisle or is_historic_order or not_a_web_order:
        LOGGER.info('Message is not an active Shopify order and will be ignored.')
        return True

    currency = customer_order['currency_code']
    shopify_order_id = Utils.get_extended_attribute(customer_order['extended_attributes'], 'order_id')
    shopify_handler = get_shopify_handler(currency)

    if shopify_handler.count_fulfillments(shopify_order_id) >= len(customer_order['shipments']):
        LOGGER.info(f'Shopify order {customer_order["sales_order_external_id"]} already fulfilled. Ignore event.')
        return True

    shopify_order = shopify_handler.get_order(shopify_order_id, 'line_items')
    item_lines = parse_shipped_item_lines(customer_order, fulfillment_event, shopify_order)

    if not item_lines:
        LOGGER.warning('No fulfillable products were found to create a fulfillment on Shopify. Ignore event.')
        return True

    shopify_location_id = await get_shopify_location_id(fulfillment_event.get('fulfillment_location_id'), currency)

    LOGGER.info(f'loc is {shopify_location_id}')

    if shopify_location_id is None:
        raise Exception(f'Unable to find shopify location ID for channel {Utils.get_shopify_channel(customer_order)}')

    fulfillment = parse_fulfillment(customer_order, item_lines, shopify_location_id, fulfillment_event)

    LOGGER.info(f'Creating fulfillment for shopify order {shopify_order_id} with: \n{json.dumps(fulfillment, indent=4)}')
    response = shopify_handler.create_fulfillment(shopify_order_id, fulfillment, True)

    error = response.get('error') if 'error' in response else response.get('errors')
    if error and error is not None and not isinstance(error, str) and error.get('base')[0] in \
            ['None of the items are stocked at the new location.', 'All line items must be stocked at the same location.']:
        for items in fulfillment_event['items']:
            product_id = items.get('product_id')
            inv_item_id = await Utils.get_shopify_conn(currency).get_inventory_item_id(product_id)

            LOGGER.info(f'inventory item id: {inv_item_id}')
            inventory_levels = await Utils.get_shopify_conn(currency).get_inventory_level(inv_item_id, shopify_location_id)

            if not inventory_levels:
                LOGGER.info(f"There's no inventory level for inventory item {inv_item_id} " \
                            f"on location {shopify_location_id}, create it with ATP 0.")
                await Utils.get_shopify_conn(currency).set_inventory_level(inv_item_id, shopify_location_id, atp=0)
                LOGGER.info(f'The inventory for the item {inv_item_id} was set to zero')
            else:
                LOGGER.info('Inventory set correctly.')
        final_response = shopify_handler.create_fulfillment(shopify_order_id, fulfillment, True)
        LOGGER.info(f'After setting inventory to zero, created fulfillment with {final_response}')
        LOGGER.info('fulfilled the request correctly.')
    elif error and error is not None:
        LOGGER.error('The following error was returned by Shopify while trying to create the fulfillment: ' \
                     f'{json.dumps(error, indent=4)}')
        raise Exception("Couldn't create fulfillment on Shopify")
    LOGGER.info('Fulfillment created successfuly')
    return True


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


def parse_shipped_item_lines(customer_order, fulfillment_event, shopify_order):
    fulfillable_products = {str(product['id']): product['fulfillable_quantity'] for product in shopify_order['line_items']}
    LOGGER.info(f'Fulfillable products: \n{json.dumps(fulfillable_products, indent=4)}')
    products_shipped = {}
    for product in customer_order['products']:
        # When product is swapped we don't send fulfillment for it
        if product['is_swapped']:
            continue

        # If the id of the fulfillment is present in the shipment_id of the product, then the product was
        # shipped in this fulfillment
        if fulfillment_event['id'] not in product['shipment_id']:
            continue

        if product['fulfillment_location'] != fulfillment_event['fulfillment_location_id']:
            continue

        item_line_id = Utils.get_extended_attribute(product.get('extended_attributes', {}), 'external_item_id')
        if not item_line_id:
            raise Exception(f"Product {product['id']} from order {customer_order['sales_order_external_id']} "\
                "does not have external_item_id extended attribute")

        # If the product has fulfillable quantity
        LOGGER.info(f'Fulfillable quantity for {item_line_id}: {fulfillable_products.get(str(item_line_id))}')
        if fulfillable_products.get(str(item_line_id), 0) > 0:
            if item_line_id in products_shipped:
                products_shipped[item_line_id] += 1
            else:
                products_shipped[item_line_id] = 1

            fulfillable_products[item_line_id] -= 1

    item_lines = []
    for item_line in products_shipped:
        item_lines.append({
            'id': item_line,
            'quantity': products_shipped[item_line]
            })

    return item_lines


def parse_fulfillment(customer_order, item_lines, shopify_dc_location_id, fulfillment_event):
    tracking_numbers = []
    tracking_urls = []
    carrier = ''  # Default shipping carrier

    products_shipped = {}
    for product in customer_order['products']:
        if product['is_swapped']:
            continue

        shipment_id = product['shipment_id']
        shipment_id_hash = shipment_id.split("-shipment-")[0]

        if shipment_id_hash != fulfillment_event['id']:
            continue

        if product['fulfillment_location'] != fulfillment_event['fulfillment_location_id']:
            continue

        item_line_id = Utils.get_extended_attribute(product.get('extended_attributes', {}), 'external_item_id')

        # using unique shipment mapping for right product ids

        if product['shipment_id'] in products_shipped:
            products_shipped[product['shipment_id']].append(item_line_id)
        else:
            products_shipped[product['shipment_id']] = [item_line_id]

    for shipment in customer_order['shipments']:
        if shipment['id'] in products_shipped:
            if shipment['carrier']:
                carrier = shipment['carrier']
            if 'tracking_code' in shipment and shipment['tracking_code']:
                tracking_numbers.append(shipment['tracking_code'])
            if 'tracking_url' in shipment and shipment['tracking_url']:
                tracking_urls.append(shipment['tracking_url'])

    return {
        'fulfillment': {
            'location_id': shopify_dc_location_id,
            'tracking_company': carrier,
            'tracking_numbers': tracking_numbers,
            'tracking_urls': tracking_urls,
            'notify_customer': True,
            'line_items': item_lines
        }
    }


async def get_shopify_location_id(nom_fulfillment_location_id, currency):
    if nom_fulfillment_location_id is None:
        raise Exception('Did not find a fulfillment_location_id with the NOM fulfillment request.')
    if nom_fulfillment_location_id not in DC_LOCATION_ID_MAP:
        raise Exception(f'No mapping for the fulfillment_location_id found in the NOM fulfillment request:'
                        f' {nom_fulfillment_location_id}. Current mapped values are: {DC_LOCATION_ID_MAP}.')

    return DC_LOCATION_ID_MAP.get(nom_fulfillment_location_id, {}).get(currency.lower(), None)
