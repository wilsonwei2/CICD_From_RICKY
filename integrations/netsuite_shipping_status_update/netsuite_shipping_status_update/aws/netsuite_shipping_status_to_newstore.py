# -*- coding: utf-8 -*-
# Copyright (C) 2020, 2021 NewStore, Inc. All rights reserved.

# Runs startup processes (expecting to be 'unused')
import netsuite.netsuite_environment_loader  # pylint: disable=W0611

import logging
import json
import asyncio
import os
import boto3


from netsuite_shipping_status_update.transformers.retrieve_netsuite_data import (
    RetrieveNetsuiteItem,
)

from netsuite.client import client as netsuite_client, make_passport
from netsuite.service import (
    CustomFieldList,
    BooleanCustomFieldRef,
    ItemFulfillment,
)

from newstore_adapter.connector import NewStoreConnector
from param_store.client import ParamStore

LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in [
    'debug'] else logging.INFO
LOGGER = logging.getLogger()
LOGGER.setLevel(LOG_LEVEL)

TENANT = os.environ['TENANT']
STAGE = os.environ['STAGE']
PARAM_STORE = ParamStore(TENANT, STAGE)
NETSUITE_SEARCH_PAGE_SIZE = os.environ['NETSUITE_SEARCH_PAGE_SIZE']
FULFILLMENT_UPDATE_SAVED_SEARCH_ID = None
NETSUITE_SYNCED_TO_NEWSTORE_FLAG_SCRIPT_ID = None
ACTIVATE_GIFTCARD_LAMBDA_NAME = os.environ.get(
    'ACTIVATE_GIFTCARD_LAMBDA_NAME', '')


def handler(event, context):
    global FULFILLMENT_UPDATE_SAVED_SEARCH_ID
    global NETSUITE_SYNCED_TO_NEWSTORE_FLAG_SCRIPT_ID
    netsuite_config = json.loads(PARAM_STORE.get_param('netsuite'))
    FULFILLMENT_UPDATE_SAVED_SEARCH_ID = netsuite_config['fulfillment_update_saved_search_id']
    NETSUITE_SYNCED_TO_NEWSTORE_FLAG_SCRIPT_ID = netsuite_config[
        'item_fulfillment_processed_flag_script_id']
    #NETSUITE_GIFTCARD_ITEM_ID = netsuite_config['netsuite_p_gift_card_item_id']

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(sync_fulfillments_from_netsuite())
    loop.stop()
    loop.close()


async def sync_fulfillments_from_netsuite():
    order_tracking_data, search_results, giftcards_data = await get_item_fulfillment_from_netsuite()

    activate_giftcard(giftcards_data)

    LOGGER.info(f'order_tracking_data: {order_tracking_data}')
    LOGGER.info(f'search results variable: {search_results}')

    if len(search_results) > 0:
        LOGGER.info(f'Send item fulfillment updates to Newstore')

        processed_to_newstore = send_updates_to_newstore(order_tracking_data)
        mark_fulfillment_items_imported(search_results, processed_to_newstore)
    else:
        LOGGER.info(f'No Item Fulfillments to process')


async def get_item_fulfillment_from_netsuite():
    retrieve_netsuite_item = RetrieveNetsuiteItem(search_page_size=NETSUITE_SEARCH_PAGE_SIZE,
                                                  saved_search_id=FULFILLMENT_UPDATE_SAVED_SEARCH_ID)
    order_tracking_data, search_results, giftcards_data = await retrieve_netsuite_item.get_item_fulfillment()

    if not search_results:
        LOGGER.info('No Fulfillment data to process')
        return [], [], []
    return order_tracking_data, search_results, giftcards_data


def activate_giftcard(giftcards_data):
    LOGGER.info(f'Giftcards data: {giftcards_data}')
    if giftcards_data:
        flat_list_giftcards_data = [
            item for sublist in giftcards_data for item in sublist]
        for giftcard in flat_list_giftcards_data:
            LOGGER.info(f'Activating Giftcard: {giftcard}')
            giftcard_activation_data = giftcard['activation_data']

            session = boto3.session.Session()
            lambda_cli = session.client('lambda')
            lambda_cli.invoke(
                FunctionName=ACTIVATE_GIFTCARD_LAMBDA_NAME,
                InvocationType='Event',
                Payload=json.dumps(
                    {"path": "/gift_card/activate", "body": json.dumps(giftcard_activation_data)})
            )


def send_updates_to_newstore(order_data):
    newstore_config = json.loads(PARAM_STORE.get_param('newstore'))
    newstore_handler = NewStoreConnector(
        tenant=TENANT,
        context={},
        host=newstore_config['host'],
        username=newstore_config['username'],
        password=newstore_config['password']
    )

    LOGGER.info(f'Send updates for newstore for order data: {order_data}')

    order_fulfillment_data = get_fulfillment_requests_from_graphql(
        order_data, newstore_handler)
    processed_to_newstore = []

    LOGGER.info(f'Got Fulfillment data from NewStore {order_fulfillment_data}')

    for order_id in order_data:
        order_data_from_netsuite = order_data[order_id]

        for netsuite_result in order_data_from_netsuite:
            # order_tracking_data[order_id] = [{
            #     'product_ids': product_ids,
            #     'tracking_number': package_tracking_number,
            #     'carrier': carrier,
            #     'order_id': order_id,
            #     'location': location,
            #     'document_number': if_document_number
            # }]

            is_order_existing = order_id in order_fulfillment_data
            if not is_order_existing:
                LOGGER.info(
                    f'Order {order_id} doesnt exist in Netsuite - Skipping')
                continue
            for fulfillment_request in order_fulfillment_data[order_id]:
                location = netsuite_result['location']

                LOGGER.info(
                    f'Check location against FFR {location} -- {fulfillment_request}')

                if location == fulfillment_request['fulfillment_node_id'] or location == fulfillment_request['fulfillment_location_id']:

                    ffr_id = fulfillment_request['fulfillment_request_id']
                    tracking_number = netsuite_result['tracking_number']
                    carrier = netsuite_result['carrier']

                    # only use items which are in the current ffr
                    product_ids = filter_ffr_product_ids(
                        netsuite_result['product_ids'], fulfillment_request['items'])
                    if len(product_ids) == 0:
                        LOGGER.info(
                            f'Fulfillment {ffr_id} does not contain any product ids of the Netsuite ItemFulfillment - skipping...')
                        continue

                    request_body = build_newstore_shipment_request(
                        product_ids, tracking_number, carrier)

                    # send shipping update to Newstore
                    LOGGER.info(f'FFR shipping update body: {request_body}')
                    shipping_update_success = newstore_handler.send_shipment(
                        ffr_id, request_body)
                    if shipping_update_success:
                        # update list of processed FFR items
                        if 'document_number' in netsuite_result:
                            processed_to_newstore.append(
                                netsuite_result['document_number'])
                    else:
                        LOGGER.error(
                            f'Failed to update shipping for Fulfillment Request {ffr_id} for order {order_id} ')

    return processed_to_newstore


def get_fulfillment_requests_from_graphql(order_data, newstore_handler):
    # TODO update item filter!
    graphql_query = """
        query Orders($order_ids: [String!]) {
            orders(first: 100, filter: {externalId: {in: $order_ids}}) {
                nodes {
                    id
                    fulfillmentRequests(first: 50) {
                        nodes {
                            id
                            items(filter: {status: {notIn: ["cancelled", "on_hold", "completed", "rejected"]}}) {
                                nodes {
                                    id
                                    status
                                    shippedAt
                                    productId
                                    carrier
                                    trackingCode
                                }
                            }
                            fulfillmentLocationId
                            nodeId
                            serviceLevel
                        }
                    }
                    externalId
                }
            }
        }
    """

    order_ids = []

    for order_id in order_data:
        order_ids.append(order_id)

    data = {
        "query": graphql_query,
        "variables": {
            "order_ids": order_ids
        }
    }

    graphql_response = newstore_handler.graphql_api_call(data)
    LOGGER.info(f"GraphQL response {graphql_response}")
    orders = graphql_response['data']['orders']['nodes']

    order_fulfillment_data = {}

    for order in orders:
        if order['fulfillmentRequests']['nodes']:
            order_fulfillment_data[order['externalId']] = []

            for ffr in order['fulfillmentRequests']['nodes']:
                ffr_row = {
                    'fulfillment_request_id': ffr['id'],
                    'fulfillment_node_id': ffr['nodeId'],
                    'fulfillment_location_id': ffr['fulfillmentLocationId'],
                    'items': []
                }

                for item in ffr['items']['nodes']:
                    ffr_row['items'].append({
                        'product_id': item['productId'],
                        'tracking_code': item['trackingCode'],
                        'carrier': item['carrier']
                    })

                order_fulfillment_data[order['externalId']].append(ffr_row)

    return order_fulfillment_data


#
# Checks which product ids from Netsuite are in the fullfillment of NewStore and only returns
# these product ids.
#
def filter_ffr_product_ids(netsuite_product_ids, fulfillment_items):
    filtered_item_ids = []
    for item in fulfillment_items:
        if item['product_id'] in netsuite_product_ids:
            filtered_item_ids.append(item['product_id'])

    return filtered_item_ids


#
# Builds the shipment request which is injected into Newstore using the data
# we mapped before from Netsuite.
#
def build_newstore_shipment_request(product_ids, tracking_number, carrier):
    request_body = {}

    shipment = {}
    shipment['tracking_code'] = tracking_number
    # carrier can be False and NOM doesn't accept it, so pass empty string instead if it's False
    shipment['carrier'] = carrier or ''

    if shipment['carrier']:
        tracking_url = get_shipping_carrier_url(
            carrier, tracking_number)
        if tracking_url:
            shipment['tracking_url'] = tracking_url

    line_items = {}
    line_items['product_ids'] = product_ids
    line_items['shipment'] = shipment

    request_body['line_items'] = [line_items]

    return request_body


# Used this link as a reference for generating the URL.
def get_shipping_carrier_url(carrier, tracking_code):
    if carrier == 'Canada Post':
        return 'https://www.canadapost-postescanada.ca/track-reperage/en#/search?searchFor='+str(tracking_code)
    if carrier == 'UPS':
        return 'https://www.ups.com/track?loc=en_US&tracknum='+str(tracking_code)
    if carrier == 'USPS':
        return 'https://tools.usps.com/go/TrackConfirmAction.action?tLabels='+str(tracking_code)

    LOGGER.error(f'Carrier {carrier} not mapped to get shipping carrier URL.')

    return ''

#
# Extracts the fulfillment item IDs from the mapped search results and calls for them to be updated in NetSuite
# :param mapped_results: The mapped results of the fulfillment items custom search
#


def mark_fulfillment_items_imported(mapped_results, processed_to_newstore):
    for result in mapped_results:
        internal_id = result['itemFulfillmentInternalId']
        tran_id = result['tranId']
        if tran_id in processed_to_newstore:
            mark_fulfillment_item_imported_by_newstore(internal_id)
            sales_order_id = result['salesOrder']
            LOGGER.info(
                f'Netsuite Fulfillment Document with IF Document number -- {tran_id} and sales order id {sales_order_id} MARKED AS FULFILLED')
        else:
            sales_order_id = result['salesOrder']
            LOGGER.info(
                f'Netsuite Fulfillment Document with IF Document number -- {tran_id} and sales order id {sales_order_id} FAILED TO INJECT')


#
# Updates the synced to newstore flag for a fulfillment item
# :param internal_id: The ID of the fulfillment item to update
#
def mark_fulfillment_item_imported_by_newstore(internal_id):
    try:
        newstore_synced_field = BooleanCustomFieldRef()
        newstore_synced_field.scriptId = NETSUITE_SYNCED_TO_NEWSTORE_FLAG_SCRIPT_ID
        newstore_synced_field.value = True

        item_fulfillment = ItemFulfillment(
            internalId=internal_id,
            customFieldList=CustomFieldList([newstore_synced_field])
        )

        response = netsuite_client.service.update(item_fulfillment,
                                                  _soapheaders={
                                                      'tokenPassport': make_passport()
                                                  })
        LOGGER.info(f'mark fulfillment item imported - response: {response}')
        if response.body.writeResponse.status.isSuccess:
            LOGGER.info(
                f'Marked fulfillment item with id "{internal_id}" as imported by NewStore in Netsuite.')
        else:
            LOGGER.error(f'Failed to mark fulfillment item with id "{internal_id}"'
                         f' as imported by NewStore in Netsuite. Response: {response.body}')
    except Exception as e:  # pylint: disable=broad-except
        LOGGER.error(f'Error while marking the fulfillment item with id "{internal_id}"'
                     f' as imported by NewStore in Netsuite. Error: {e}')
