# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.

# Runs startup processes
import netsuite.netsuite_environment_loader  # pylint: disable=W0611
import netsuite.api.sale as netsuite_sale
from netsuite.api.item import get_product_by_sku
import logging
import json
import asyncio
import netsuite_transfer_updates_to_netsuite.transformers.process_item_fulfillment as pif
import netsuite_transfer_updates_to_netsuite.helpers.sqs_consumer as sqs_consumer
from netsuite_transfer_updates_to_netsuite.helpers.utils import Utils
from zeep.helpers import serialize_object
from newstore_adapter.utils import get_extended_attribute


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
SQS_QUEUE = Utils.get_environment_variable(
    "SQS_QUEUE", "frankandoak-tu-asn-created-queue.fifo")
LOGGER.info(F"SQS Queue {SQS_QUEUE}")
EVENT_ID_CACHE = Utils.get_environment_variable(
    "EVENT_ID_CACHE", "tu-asn-created-event-id-cache")
LOGGER.info(f"EVENT_ID_CACHE {EVENT_ID_CACHE}")
DYNAMO_TABLE = Utils.get_dynamo_table(EVENT_ID_CACHE)

#ptvsd.enable_attach(address=('localhost', 65531), redirect_output=True)
# ptvsd.wait_for_attach()

# We will limit this to clearing once per instantiation to limit overhead

Utils.clear_old_events(dynamo_table=DYNAMO_TABLE, days=7)


def handler(_, context):
    """
    Receives event payloads from an SQS queue. The payload is taken from the order
    event stream, detailed here:
        https://apidoc.newstore.io/newstore-cloud/hooks_eventstream.html
    Event Type: inventory_transaction.asn_created
    """
    LOGGER.info(f'Beginning queue retrieval...')
    Utils.get_newstore_conn(context)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = sqs_consumer.consume(process_inventory_adj, SQS_QUEUE)
    loop.run_until_complete(task)
    loop.stop()
    loop.close()


async def process_inventory_adj(message):
    LOGGER.info(f"Message to process: \n {json.dumps(message, indent=4)}")
    asn_created_event = message['payload']

    if Utils.event_already_received(f"{asn_created_event['id']}-{asn_created_event['chunk_number']}", DYNAMO_TABLE):
        LOGGER.info('Event was already processed, skipping')
        return True

    transfer_order = await get_transfer_order(asn_created_event['transfer_order_ref'])
    transfer_order = serialize_object(transfer_order)
    LOGGER.info(
        f'TransferOrder: \n{json.dumps(transfer_order, indent=4, default=Utils.json_serial)}')
    item_fulfillment = netsuite_sale.initialize_record(
        'itemFulfillment', 'transferOrder', transfer_order['internalId'])
    if not item_fulfillment:
        raise Exception('Not able to initialize item fulfillment.')

    item_fulfillment = serialize_object(item_fulfillment)
    LOGGER.info(
        f'Initialized ItemFulfillment: \n{json.dumps(item_fulfillment, indent=4, default=Utils.json_serial)}')

    store, products_info = get_store_and_products_from_nom(
        asn_created_event['items'], asn_created_event['origin_id'])
    item_fulfillment_transformed = pif.transform_item_fulfillment(
        asn_created_event, products_info, store, item_fulfillment)
    LOGGER.info(
        f'Transformed ItemFulfillment: \n{json.dumps(serialize_object(item_fulfillment_transformed), indent=4, default=Utils.json_serial)}')

    result = netsuite_sale.create_item_fulfillment(
        item_fulfillment_transformed)
    if result:
        LOGGER.info(
            f'Item Fulfillment successfully created in NetSuite internal ID {result}')
        Utils.mark_event_as_received(
            f"{asn_created_event['id']}-{asn_created_event['chunk_number']}", DYNAMO_TABLE)
    else:
        LOGGER.error(f'Error creating Item Fulfillment in NetSuite: {result}')

    return bool(result)


def get_store_and_products_from_nom(items, fulfillment_node_id):
    output = []
    product_ids = {item['product_id']: item['quantity'] for item in items}

    store_id = Utils.get_nws_location_id(fulfillment_node_id)
    store = Utils.get_store(store_id)

    for product_id in product_ids:
        product = Utils.get_product(product_id, store.get(
            'catalog', 'storefront-catalog-en'), store.get('locale', 'en-US'))
        assert product, f"Product with ID {product_id} couldn't be fetched from NOM."

        netsuite_internal_id = get_extended_attribute(
            product.get('extended_attributes', []), 'variant_nsid')
        if netsuite_internal_id:
            LOGGER.info(
                f'Product NetSuite internal id {netsuite_internal_id} found for product {product_id}')
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
                raise Exception(
                    f'Item/Product {product_id} not found on NetSuite.')

    return store, output


async def get_transfer_order(tran_id):
    _, transfer_order = netsuite_sale.get_transaction_with_tran_id(tran_id)
    if not transfer_order:
        raise Exception(f'TransferOrder {tran_id} not found on NetSuite.')
    return transfer_order
