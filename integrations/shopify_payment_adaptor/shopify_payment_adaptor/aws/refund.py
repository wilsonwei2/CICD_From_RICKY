# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.
import os
import logging
import json
import asyncio
import aiohttp
import time

from dataclasses import asdict
from dacite import from_dict
from uuid import uuid4

import shopify_payment_adaptor.utils.utils as utils
import shopify_payment_adaptor.aws.gift_cards as gift_cards
from shopify_payment_adaptor.aws.revoke import create_refund
from shopify_payment_adaptor.aws.transformer import parse_json_to_calculate_refund, parse_json_to_create_refund, create_shopify_refund_body
from shopify_payment_adaptor.models.newstore_note import OrderNotes

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


NS_HANDLER = utils.get_newstore_handler()

# This is used as a flag to enable certain test features for running in sandbox environment.
# (e.g., sleep and wait for short time period to avoid race conditions to make testing easier,
# rather than implementing workarounds involving queues and/or the boto module).
SANDBOX_MODE = os.environ.get('SANDBOX_MODE', '') in ('true', '1', 't')


def handler(event, context):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(
        _push_refund_to_shopify(
            body=json.loads(event['body']),
            financial_instrument_id=event['pathParameters']['financial_instrument_id']
        )
    )
    loop.stop()
    loop.close()
    return result


async def _push_refund_to_shopify(body, financial_instrument_id):
    try:
        LOGGER.info(f'Processing refund: ${json.dumps(body, indent=4)}')
        order_id, return_id = (
            body['account_id'],
            body['idempotency_key']
        )
        transactions = []
        transaction = next((x for x in body.get(
            'transactions', []) if x.get('reason') == 'capture'), None)
        assert transaction, 'Transaction for refund not found'
        metadata = body.get('metadata', {})
        amount_info = body.get('arguments')
        customer_order = await NS_HANDLER.get_customer_order(order_id)
        customer_order = customer_order.get('customer_order', {})
        shopify_handler = utils.get_shopify_handler()
        canceled_items = _get_cancelled_items(customer_order)
        is_not_return = False
        is_exchanged = False
        amount_info = body.get('arguments')

        notes = await _get_order_notes(order_id=order_id)
        LOGGER.info(f"Order note: {asdict(notes)}")
        note_id = _get_loop_exchange_note_id(order_notes=notes)
        if note_id is not None:
            LOGGER.info('Process instrument that is handled by the Loop Returns extension, do not call shopify refund')
            await _delete_order_note(order_id=order_id, note_id=note_id)

            transactions.append({
                'transaction_id': str(uuid4()),
                'refund_amount': -float(amount_info.get('amount')),
                'instrument_id': financial_instrument_id,
                'reason': 'refund',
                'payment_method': transaction['payment_method'],
                'currency': transaction['currency'],
                'metadata': body['metadata']
            })
            refund_response = transactions
            return {
                'statusCode': 200,
                'body': json.dumps(refund_response)
            }

        if not _is_reduction_revoke(return_id) and not _is_reduction_cancel(return_id):
            ns_return = None
            try:
                ns_refund = (await NS_HANDLER.get_refund(order_id, return_id)).get('refund', {})
                LOGGER.info(f'Processing a refund {json.dumps(ns_refund)}')
                if _is_not_return(ns_refund):
                    is_exchanged = order_id != ns_refund['order_id']
                else:
                    ns_return = await NS_HANDLER.get_return_orders(order_id, return_id)
            except Exception:
                LOGGER.exception(
                    'Failed to get the refund, validating if is a refund from a cancellation due to precaptured')
                # When part of the order is fulfilled and the remaining items are canceled
                # Refund the canceled items on Shopify
                if len(canceled_items) > 0:
                    LOGGER.info('Processing a refund for cancelled items ...')
                    ns_return = {
                        'return_items': canceled_items
                        }
                if not ns_return:
                    ns_return = {'is_reduction': True}

        elif _is_reduction_revoke(return_id):
            # Reduction revoke will have the items returned in the revoke call
            ns_return = {
                'return_items': canceled_items
                }

        elif _is_reduction_cancel(return_id) or is_not_return:
            ns_return = {'is_reduction': True}
        else:
            ns_return = await NS_HANDLER.get_return_orders(order_id, return_id)

        if utils.is_capture_credit_card(transaction['payment_method']) and metadata.get('shopify_order_id') and not metadata.get('extended_attributes'):
            # This is a refund for a purchase originally placed via Shopify using credit card
            LOGGER.info(
                'Creating a refund of a credit card for a shopify created order...')
            if SANDBOX_MODE:
                time.sleep(5)
            shopify_order_id = metadata['shopify_order_id']
            # # We originally attempt to pull returns from NS so we can get the item list
            # try:
            #     ns_return = await NS_HANDLER.get_return_orders(order_id, return_id)
            # except aiohttp.client_exceptions.ClientResponseError:
            #     # If there is no associated return (e.g. an appeasement) then we just issue a refund transaction
            #     LOGGER.info(
            #         'No associated return, validating appeasment or cancellation refund')
            # Retrieve associated Shopify order with the fields specified included
            shopify_order = await shopify_handler.get_order(
                shopify_order_id, 'id,line_items,name,total_price,customer,refunds')
            if not _check_refund_exists(shopify_order.get('refunds', []), metadata):
                LOGGER.info('This refund does not exist, we will create it')
                json_to_calculate_refund = await parse_json_to_calculate_refund(
                    ns_return, shopify_order, customer_order, is_exchanged)
                LOGGER.info(f'Json to calculate refund on Shopify: ${json.dumps(json_to_calculate_refund, indent=4)}')

                # Shopify will actually calculate the refund based on the order and line items being returned
                calculated_refund_json = await shopify_handler.calculate_refund(
                    shopify_order_id, json_to_calculate_refund)

                # If we receive a valid refund response we can proceed to create and process the refund
                if calculated_refund_json:
                    # Creates the refund request object to be passed to Shopify
                    json_to_create_refund = await parse_json_to_create_refund(
                        calculated_refund_json, ns_return, shopify_order, json_to_calculate_refund['refund']['refund_line_items'], amount_info)
                    LOGGER.info(f'Json to create refund on Shopify: ${json.dumps(json_to_create_refund, indent=4)}')

                    # Initiate the actual refund with Shopify
                    response = await shopify_handler.create_refund(
                        order_id=shopify_order_id,
                        data=json_to_create_refund
                    )
                    LOGGER.info(f'refunded {json.dumps(response)}')
                    # Populate a transaction object with the Shopify response params, this is stored as a record and returned to the caller
                    for transaction_shopify in response['refund']['transactions']:
                        transactions.append({
                            'transaction_id': str(uuid4()),
                            'refund_amount': -float(transaction_shopify.get('amount')),
                            'instrument_id': financial_instrument_id,
                            'reason': 'refund',
                            'payment_method': transaction['payment_method'],
                            'currency': transaction['currency'],
                            'metadata': body['metadata']
                        })
            else:
                for refund in shopify_order['refunds']:
                    # In case of exchange in Returnly refund won't have transactions
                    refund_transactions = refund.get('transactions', [])
                    if refund_transactions:
                        for transaction_shopify in refund['transactions']:
                            transactions.append({
                                'transaction_id': str(uuid4()),
                                'refund_amount': -float(amount_info.get('amount')),
                                'instrument_id': financial_instrument_id,
                                'reason': 'refund',
                                'payment_method': transaction['payment_method'],
                                'currency': transaction['currency'],
                                'metadata': body['metadata']
                            })
                    elif 'Returnly' in refund.get('note'):
                        transactions.append({
                            'transaction_id': str(uuid4()),
                            'refund_amount': -0.0,  # When exchange refund is 0
                            'instrument_id': financial_instrument_id,
                            'reason': 'refund',
                            'payment_method': transaction['payment_method'],
                            'currency': transaction['currency'],
                            'metadata': {**body['metadata'], 'returnly_exchange': 'True'}
                        })

        elif utils.is_capture_gift_card(transaction['payment_method']) and metadata.get('shopify_order_id'):
            LOGGER.info(
                'Creating a refund of a gift card for a shopify created order.')
            if SANDBOX_MODE:
                time.sleep(5)
            shopify_order_id = body['metadata']['shopify_order_id']
            try:
                ns_return = await NS_HANDLER.get_return_orders(order_id, return_id)
            except aiohttp.client_exceptions.ClientResponseError:
                # If there is no associated return (e.g. an appeasement) then we just issue a refund transaction
                LOGGER.info(
                    "No associated return, assuming appeasement return")
                return await _handle_order_refund_appeasement_transaction(transaction,
                                                                          amount_info,
                                                                          shopify_order_id,
                                                                          body,
                                                                          financial_instrument_id,
                                                                          metadata
                                                                          )
            shopify_order = await shopify_handler.get_order(
                shopify_order_id, 'id,line_items,name,total_price,customer,email,refunds')
            LOGGER.debug(json.dumps(shopify_order, indent=4))
            json_to_calculate_refund = await parse_json_to_calculate_refund(
                ns_return, shopify_order, customer_order, is_exchanged)
            LOGGER.info(f'Json to calculate refund on Shopify: ${json.dumps(json_to_calculate_refund, indent=4)}')

            calculated_refund_json = await shopify_handler.calculate_refund(
                shopify_order_id, json_to_calculate_refund)
            ns_return['refunded_amount'] = 0
            if calculated_refund_json:
                json_to_create_refund = await parse_json_to_create_refund(
                    calculated_refund_json, ns_return, shopify_order, json_to_calculate_refund['refund']['refund_line_items'], amount_info)
                LOGGER.info(f'Json to create refund on Shopify: ${json.dumps(json_to_create_refund, indent=4)}')

            response = await shopify_handler.create_refund(
                order_id=shopify_order_id,
                data=json_to_create_refund
            )
            gift_card_response = await gift_cards.activate_card(amount_info.get('amount'), amount_info.get('currency'), shopify_order.get('customer', {})['id'])
            body['metadata']['number'] = gift_card_response.get(
                'gift_card', {}).get('id')
            transactions.append({
                'transaction_id': str(uuid4()),
                'refund_amount': -float(gift_card_response['gift_card']['balance']),
                'instrument_id': financial_instrument_id,
                'reason': 'refund',
                'payment_method': transaction['payment_method'],
                'currency': transaction['currency'],
                'metadata': body['metadata']
            })
        elif utils.is_capture_gift_card(transaction['payment_method']) and metadata.get('order_id'):
            LOGGER.info(
                'Creating a refund of a credit card for a associate created order...')
            LOGGER.info('creating a new gift card and refunding to it...')
            sp_order = await NS_HANDLER.get_order(order_id)
            assert sp_order.get('customer', {}).get(
                'email'), 'Could not find email to refund gift card to..'
            order_email = sp_order.get('customer', {})['email']
            customers = await shopify_handler.search_customer_by_email(order_email)
            if len(customers.get('customers', [])) < 1:
                LOGGER.info(
                    'Customer not found, creating it at shopify')
                order_name = sp_order.get('customer', {}).get('name')
                response = await shopify_handler.create_customer(order_email, order_name)
                customer = response.get('customer')
            else:
                customer = customers.get('customers', [{}])[0]
            LOGGER.info(customer)
            gift_card_response = await gift_cards.activate_card(amount_info.get('amount'), amount_info.get('currency'), customer.get('id'))
            body['metadata']['number'] = gift_card_response.get(
                'gift_card', {}).get('id')
            transactions.append({
                'transaction_id': str(uuid4()),
                'refund_amount': -float(gift_card_response['gift_card']['balance']),
                'instrument_id': financial_instrument_id,
                'reason': 'refund',
                'payment_method': transaction['payment_method'],
                'currency': transaction['currency'],
                'metadata': body['metadata']
            })
        else:
            LOGGER.info('Process instrument that is pre-refunded already...')
            transactions.append({
                'transaction_id': str(uuid4()),
                'refund_amount': -float(amount_info.get('amount')),
                'instrument_id': financial_instrument_id,
                'reason': 'refund',
                'payment_method': transaction['payment_method'],
                'currency': transaction['currency'],
                'metadata': body['metadata']
            })
        refund_response = transactions
        return {
            'statusCode': 200,
            'body': json.dumps(refund_response)
        }

    except aiohttp.client_exceptions.ClientConnectorError as ex:
        LOGGER.exception('Error connecting with shopify:')
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error_code': 'connection_error',
                'message': str(ex)
            })
        }
    except Exception as ex:
        LOGGER.exception('Error processing refund')
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error_code': 'unexpected_error',
                'message': str(ex)
            })
        }


def _get_refund_id_if_exists(metadata: dict) -> str:
    ext_attrs = metadata.get('extended_attributes', [])
    return next((attr['value'] for attr in ext_attrs if attr.get('name') == 'shopify_refund_id'), None)


async def _handle_order_refund_appeasement_transaction(transaction,
                                                       amount_info,
                                                       shopify_order_id,
                                                       body,
                                                       financial_instrument_id,
                                                       metadata):
    # Find the associated Shopify transaction to determine the proper 'parent_id' for the refund
    shopify_handler = utils.get_shopify_handler()
    refund_id = _get_refund_id_if_exists(metadata)
    if refund_id:
        refund_data = await shopify_handler.get_refund(shopify_order_id, refund_id)
        if refund_data and refund_data.get('refund', {}).get('processed_at'):
            LOGGER.info('Historical refund instrument, already refunded..')
            refund_response = [{
                'transaction_id': str(uuid4()),
                'refund_amount': -float(amount_info.get('amount')),
                'instrument_id': financial_instrument_id,
                'reason': 'refund',
                'payment_method': transaction['payment_method'],
                'currency': transaction['currency'],
                'metadata': body['metadata']
            }]
    else:
        shopify_transactions = await shopify_handler.get_transactions_for_order(shopify_order_id)
        LOGGER.info(
            "Shopify transactions for order {order}: {transactions}".format(order=shopify_order_id,
                                                                            transactions=json.dumps(shopify_transactions)))
        shopify_transaction = next(
            (x for x in shopify_transactions if x.get('kind') in ['capture', 'sale']), None)
        assert shopify_transaction, 'Transaction for capture/sale not found'
        # The parent_id of the transaction refund being created must be the ID of the associated
        #   `capture` or `sale` transaction where the original charge was made
        shopify_parent_transaction_id = shopify_transaction['id']

        refund_amount = str(float(amount_info.get('amount')))

        shopify_refund_transaction = await create_shopify_refund_body(refund_amount, shopify_parent_transaction_id)
        transaction_refund_response = await shopify_handler.create_transaction(
            order_id=shopify_order_id,
            data=shopify_refund_transaction
        )
        LOGGER.info("Shopify refund response: {}".format(
            json.dumps(transaction_refund_response)))
        assert transaction_refund_response, "invalid response received from Shopify"

        refund_response = [{
            'transaction_id': str(uuid4()),
            'refund_amount': -float(amount_info.get('amount')),
            'instrument_id': financial_instrument_id,
            'reason': 'refund',
            'payment_method': transaction['payment_method'],
            'currency': transaction['currency'],
            'metadata': body['metadata']
        }]
    LOGGER.info(f'Responding with: ${json.dumps(refund_response)}')
    return {
        'statusCode': 200,
        'body': json.dumps(refund_response)
    }

def _check_refund_exists(shopify_refunds, metadata):
    LOGGER.info(f'metadata is {metadata}')
    extended_attr = metadata.get('extended_attributes')
    LOGGER.info(f'attr is {extended_attr}')
    if extended_attr and type(extended_attr) == list:
        refund_transactions_ids = extended_attr[0].get('shopify_refund_transactions_ids')
        for refund in shopify_refunds:
            for transaction in refund['transactions']:
                if transaction['id'] in refund_transactions_ids and transaction['status'] not in ['failed']:
                    LOGGER.info('Refund already exists on Shopify.')
                    return True
    return False

def _get_cancelled_items(order):
    canceled_items = []
    for product in order['products']:
        if product['status'] == 'canceled':
            canceled_items.append(
                {
                    'product_id': product['id']
                    }
                )
    return canceled_items

def _is_reduction_cancel(return_id):
    return 'reduction-cancel' in return_id


def _is_reduction_revoke(return_id):
    return 'reduction-revoke' in return_id


def _is_not_return(ns_refund):
    return not bool(ns_refund['return_id'])


async def _get_order_notes(order_id: str) -> OrderNotes:
    return from_dict(data_class=OrderNotes, data=await NS_HANDLER.get_order_note(order_id))


async def _delete_order_note(order_id: str, note_id):
    await NS_HANDLER.delete_order_note(order_id=order_id, note_id=note_id)


def _get_loop_exchange_note_id(order_notes: OrderNotes):
    for note in order_notes.notes:
        if note.source == "Loop Exchange":
            return note.id
    return None
