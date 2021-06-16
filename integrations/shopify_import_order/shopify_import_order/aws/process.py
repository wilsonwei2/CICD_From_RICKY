# -*- coding: utf-8 -*-
# Copyright (C) 2015 - 2019, 2020 NewStore, Inc. All rights reserved.
import datetime
import logging
import simplejson as json
import os
from dataclasses import asdict
from typing import Dict, List
from dacite import from_dict

from shopify_import_order.models.newstore_note import NewStoreNote
from shopify_import_order.models.newstore_return import NewStoreReturn
from shopify_import_order.orders import transform
from shopify_import_order.handlers.shopify_helper import get_order_risks
from shopify_import_order.handlers.utils import Utils
from shopify_import_order.returns import NewStoreReturnService

TENANT = os.environ.get('TENANT') or 'frankandoak'
STAGE = os.environ.get('STAGE') or 'x'
LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOG_LEVEL)


def _str_2_bool(b_str):
    return b_str.lower() in ('yes', 'true', '1')


def handler(event, context): # pylint: disable=W0613
    """
    Take new shopify order from webhook call. Should include a query parameter
    denoting which shopify channel the order is coming from (e.g., 'USC').
    Transform the order into Newstore format and fulfill the order through
    Newstore's API.

    Args:
        event:
            body: Shopify order JSON.
            queryStringParameters['channel']: Shopify instance channel (e.g., 'USC')
        context: function context

    Returns:
        dict:
            statusCode: 200 or 400 depending on successful order processing
            message: 'processed' or an error message
    """
    order_body = str(event['body'])
    shop = event['shop']
    shop_id = Utils.get_instance().get_shop_id(shop)

    shopify_handler = Utils.get_instance().get_shopify_handler(shop_id)
    newstore_handler = Utils.get_instance().get_ns_handler()

    try:
        order = json.loads(order_body)

        if order.get('name').startswith('LGC'):
            LOGGER.info(f'Order is a Loop Gift Card Shopify id {order["id"]}. Name {order.get("name")}. Not injecting....')
            return {
                'statusCode':200,
                'body': 'Order is a LGC'
            }


        LOGGER.info('Calculating Order Risk')
        order_risk = _validate_order_risk(order, shop_id)
        if order_risk:
            LOGGER.info(f'Order with Shopify ID {order["id"]} is at risk state. Not injecting....')
            return {
                'statusCode':200,
                'body': 'Order at Risk by Kount System not injecting into NewStore'
            }

        LOGGER.info("Shopify order Payload")
        LOGGER.info(order)

        transaction_data = get_transaction_data(shopify_handler, order)

        is_exchange = order.get('name').startswith('EXCH')
        if is_exchange:
            _create_ns_return(order, shopify_handler, newstore_handler)

        shipping_offer_token = get_shipping_offer_token(order, newstore_handler)
        ns_order = transform(transaction_data, order, is_exchange, shop, shipping_offer_token)

        response = newstore_handler.fulfill_order(ns_order)

        LOGGER.info('Response from Newstore Platform')
        LOGGER.debug(response)
        newstore_order_url = f'https://manager.{TENANT}.{STAGE}.newstore.net/sales/orders/{response.get("id")}'
        success_note_message = f'Injected into NewStore: {newstore_order_url}'
        note_and_tag_response = _update_note_on_order(shopify_handler=shopify_handler, order=order_body,
                                                      message=success_note_message, order_processed=True)
        LOGGER.debug(json.dumps(note_and_tag_response))

        return {
            'statusCode': 200,
            'body': json.dumps(response)
        }

    except Exception as ex:
        LOGGER.exception('Error transforming or injecting order')
        LOGGER.info(ex)
        try:
            note_and_tag_response = _update_note_on_order(shopify_handler=shopify_handler, order=order_body, message=str(ex),
                                                          order_processed=False)
            LOGGER.info(f'Updated the order in shopify with note - {str(ex)}')
            LOGGER.info(json.dumps(note_and_tag_response))
        except Exception:
            LOGGER.exception('Failed to report failed order injection')


def _validate_order_risk(order, shop_id):
    shopify_order_id = order['id']
    risks = get_order_risks(shopify_order_id, shop_id)
    external_risks = [risk for risk in risks if risk['source'] == 'External']
    if external_risks:
        risks = external_risks
    for risk in risks:
        LOGGER.debug(f'Risk: {risk}')
        recommendation = str(risk['recommendation'])
        LOGGER.debug(f'Shopify Order Id with id # {shopify_order_id} has recommendation level as {recommendation}')
        if 'cancel' in recommendation.lower():
            return True
    return False


def get_shipping_offer_token(order, newstore_handler):
    LOGGER.debug('Trying to get a pickup in store shipping offer token.')
    shipping_offer_token = None
    billing_address = order.get('billing_address', None)
    shipping_address = order.get('shipping_address', None)

    def get_bag_item(line_item):
        return {
            'product_id': line_item['product_id'],
            'quantity': line_item['quantity']
        }

    if shipping_address is None and billing_address is not None:
        try:
            shipping_code = order['shipping_lines'][0]['code']
            LOGGER.debug(f'Try to get geo location for shipping code: {shipping_code}')
            latitude, longitude = get_store_geo_location(shipping_code, newstore_handler)

            in_store_pickup_options = newstore_handler.get_in_store_pickup_options({
                'location': {
                    'geo': {
                        'latitude': latitude,
                        'longitude': longitude
                    }
                },
                'bag': [get_bag_item(line_item) for line_item in order.get('line_items', [])]
            }).get('options', [])

            selected_option = next(filter(lambda option: option['fulfillment_node_id'] == store_id, in_store_pickup_options), None)

            if selected_option is not None:
                shipping_offer_token = selected_option['in_store_pickup_option']['shipping_offer_token']

            LOGGER.debug(f'Got pickup in store shipping offer token: {shipping_offer_token}')
        except: # pylint: disable=W0702
            LOGGER.debug('Could not get a shipping offer token, no pickup in store.')

    return shipping_offer_token


def get_store_geo_location(store_id, newstore_handler):
    store = newstore_handler.get_store(store_id)
    latitude = store['physical_address']['latitude']
    longitude = store['physical_address']['longitude']

    return latitude, longitude


def get_transaction_data(shopify_adaptor, order):
    '''
    Function that is used to extract the transaction data -- any different kinds of payments
    that are used in whole order.
    '''
    return shopify_adaptor.transaction_data(order)


def _update_note_on_order(shopify_handler=None, order=None, message=None, order_processed=None):
    ## Checking if there are any existing notes.
    shopify_order = json.loads(order)
    order_id = shopify_order.get('id', '')
    # LOGGER.info('Updating Note and Tag for shopify order id {order_id}'.format(order_id))
    existing_note = shopify_order.get('note_attributes', [])

    for index, note in enumerate(existing_note):
        if note.get('name') == 'Newstore Status':
            existing_note.pop(index)
    existing_note.append(
        {
            'name': 'Newstore Status',
            'value': message
        }
    )
    newstore_tag = 'newstore_created' if order_processed else 'newstore_failed'
    # Checking if we have any existing tags.
    existing_tags = [tag.strip() for tag in shopify_order.get('tags', '').split(',')]
    for index, tag in enumerate(existing_tags):
        if tag in ['newstore_created', 'newstore_failed']:
            tag = existing_tags.pop(index)
    existing_tags.append(newstore_tag)

    json_object = {
        'order': {
            'id': order_id,
            'note_attributes': existing_note,
            'tags': ','.join(existing_tags)
        }
    }

    # updating shopify order with note and tags
    return shopify_handler.update_order(order_id, json_object)


def _get_note_attribute_value(order: Dict, note_attribute_name: str) -> str:
    for attribute in order.get("note_attributes"):
        if attribute.get('name') == note_attribute_name:
            return str(attribute.get('value'))
    return None


def _get_refund(original_order_refunds: List[Dict], exchange_order_date: datetime) -> Dict:
    refund = None
    refund_date = None

    for order_refund in original_order_refunds:
        order_refund_date = datetime.datetime.strptime(order_refund['created_at'], "%Y-%m-%dT%H:%M:%S%z")
        if refund_date is None:
            refund = order_refund
            refund_date = order_refund_date
        elif abs(order_refund_date - exchange_order_date) < abs(refund_date - exchange_order_date):
            refund = order_refund
            refund_date = order_refund_date

    return refund


def _all_products_returned(ns_return: NewStoreReturn, return_response: str) -> bool:
    for item in ns_return.items:
        if item.product_id not in return_response:
            return False
    return True


def _create_loop_exchange_note(original_order_id: str, exchange_date: str, exchange_name: str, newstore_handler) -> NewStoreNote:
    text = f"Return from a loop exchange order name: {exchange_name}, at {exchange_date}"
    source = "Loop Exchange"
    response = newstore_handler.create_order_note(order_id=original_order_id, text=text, source=source, tags=[])
    return from_dict(NewStoreNote, response)


def _create_ns_return(order, shopify_handler, newstore_handler):
    ns_return_service = NewStoreReturnService()

    original_order_id = _get_note_attribute_value(order=order, note_attribute_name="originating_order_id")
    original_order_refunds = shopify_handler.get_refunds(original_order_id)
    LOGGER.info(f'Original order refunds from original order id {original_order_id}')
    LOGGER.info(original_order_refunds)


    exchange_order_date = datetime.datetime.strptime(order['created_at'], "%Y-%m-%dT%H:%M:%S%z")
    refund = _get_refund(original_order_refunds["refunds"], exchange_order_date)

    ns_return = ns_return_service.create_newstore_return(shopify_refund=refund, returned_from="CA Mochila")

    original_order_name = _get_note_attribute_value(order=order, note_attribute_name="originating_order_name")
    ns_original_order = _get_newstore_original_order(original_order_name, newstore_handler)

    created_note = _create_loop_exchange_note(original_order_id=ns_original_order["order_uuid"],
                                              exchange_date=order.get('created_at', ''),
                                              exchange_name=order.get('name', ''),
                                              newstore_handler=newstore_handler)

    response = newstore_handler.create_return(ns_original_order["order_uuid"], asdict(ns_return))
    if response["repeated_returned"]:
        LOGGER.info("Delete order note because return was done already")
        newstore_handler.delete_order_note(created_note.order_id, created_note.id)
        if not _all_products_returned(ns_return, response.get("message")):
            raise Exception("The exchange contains products that some were returned already and others not returned")

def _get_newstore_original_order(external_id: str, newstore_handler) -> Dict:
    try:
        original_order = newstore_handler.get_order_by_external_id(external_id)
        return original_order
    except Exception as e:
        LOGGER.info(e)

    LOGGER.info("Check if it is a Historical Order Exchange")
    original_order = newstore_handler.get_order_by_external_id(f'HIST-{external_id}')
    return original_order
