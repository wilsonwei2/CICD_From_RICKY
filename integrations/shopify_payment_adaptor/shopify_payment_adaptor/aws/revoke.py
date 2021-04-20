# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.
import logging
import json
import asyncio
import aiohttp
from uuid import uuid4

from shopify_payment_adaptor.aws.transformer import _get_extended_attribute
from shopify_payment_adaptor.utils.utils import get_newstore_handler,  \
    get_shopify_handler, is_capture_credit_card, is_capture_gift_card, ERRORS_TO_RETRY
from shopify_payment_adaptor.aws.gift_cards import activate_card

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

NS_HANDLER = get_newstore_handler()


def handler(event, context):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(
        _push_revoke_to_shopify(
            body=json.loads(event['body']),
            financial_instrument_id=event['pathParameters']['financial_instrument_id']
        )
    )
    loop.stop()
    loop.close()
    return result


async def _push_revoke_to_shopify(body, financial_instrument_id):
    try:
        LOGGER.info(f'Processing revoke: ${json.dumps(body, indent=4)}')
        order_id = body['account_id']
        transactions = []
        amount_info = body.get('arguments')
        transaction = next((x for x in body.get(
            'transactions', []) if x.get('reason') in ['authorization', 'capture']), None)
        assert transaction, 'Transaction for revoke not found'
        shopify_handler = get_shopify_handler()
        LOGGER.info(transaction)

        if transaction and (is_capture_credit_card(transaction['payment_method'])):
            shopify_order_id = transaction['metadata'].get(
                'shopify_order_id')
            if shopify_order_id:
                transactions = await shopify_handler.get_transactions_for_order(shopify_order_id)
                LOGGER.info(f'Transactions: ${json.dumps(transactions, indent=4)}')
                auth_id = transaction.get(
                    'metadata', {}).get('shopify_auth_id')
                if check_transaction_captured(transactions):
                    LOGGER.info(
                        'Revoke of captured transaction should proceed to refund.')
                    response = await _push_captured_revoke_to_shopify(handler, body, financial_instrument_id, shopify_order_id, transactions)

                    if response['statusCode'] == 200:
                        LOGGER.info(f'Trying to cancel order with ID: ${shopify_order_id}')
                        cancel_order = await shopify_handler.cancel_order(order_id=shopify_order_id)
                        LOGGER.info(f'Cancelled response: ${json.dumps(cancel_order)}')
                    return response
                [void_transaction, cancel_order] = await asyncio.gather(
                    shopify_handler.void_transaction(
                        order_id=shopify_order_id, amount=amount_info['amount'], auth_id=auth_id),
                    shopify_handler.cancel_order(order_id=shopify_order_id)
                )
                transactions.append({
                    'transaction_id': str(uuid4()),
                    'instrument_id': financial_instrument_id,
                    'capture_amount': -(float(amount_info['amount'])),
                    'refund_amount': 0,
                    'currency': amount_info['currency'],
                    'reason': 'revoke',
                    'payment_method': transaction['payment_method'],
                    'metadata': body['metadata']
                })
            else:
                LOGGER.error(
                    'The metadata field doesn\'t contain the shopify_order_id')
        # If is gift card and Shopify order
        elif transaction and is_capture_gift_card(transaction['payment_method']) and transaction['metadata'].get('shopify_order_id'):
            LOGGER.info('Refund for Shopify order paid with gift card, cancel order in Shopify.')

            shopify_order_id = transaction['metadata'].get('shopify_order_id')

            shopify_transactions = await shopify_handler.get_transactions_for_order(shopify_order_id)
            LOGGER.info(f'Shopify transactions: ${json.dumps(shopify_transactions, indent=4)}')
            auth_id = transaction.get(
                'metadata', {}).get('shopify_auth_id')
            if check_transaction_captured(shopify_transactions):
                LOGGER.info(
                    'Revoke of captured transaction should proceed to refund.')
                response = await _push_captured_revoke_to_shopify(handler,
                                                                  body,
                                                                  financial_instrument_id,
                                                                  shopify_order_id,
                                                                  shopify_transactions)

            if response['statusCode'] == 200:
                LOGGER.info(f'Trying to cancel order with ID: ${shopify_order_id}')
                cancel_order = await shopify_handler.cancel_order(order_id=shopify_order_id)
                LOGGER.info(f'Cancelled response: ${json.dumps(cancel_order)}')

            return response
        elif transaction and is_capture_gift_card(transaction['payment_method']):
            LOGGER.info('Refund for In Store order paid with gift card, creating a new gift card and refunding to it...')
            try:
                sp_order = await NS_HANDLER.get_order(order_id)
                assert sp_order.get('customer', {}).get(
                    'email'), 'Could not find email to refund gift card to..'
                customer_email = sp_order.get('customer', {})['email']
                customer_name = sp_order.get('customer', {}).get('name')
            except Exception as ex:
                LOGGER.info("Order not fetched from NewStore, try customer order endpoint.")
                sp_order = await NS_HANDLER.get_customer_order(order_id)
                sp_order = sp_order.get('customer_order')
                assert sp_order.get('consumer', {}).get(
                    'email'), 'Could not find email to refund gift card to..'
                customer_email = sp_order.get('consumer', {})['email']
                customer_name = sp_order.get('consumer', {}).get('name')

            customer = await shopify_handler.search_customer_by_email(customer_email)
            if len(customer.get('customers', [])) < 1:
                LOGGER.info(
                    'Customer not found, creating it at shopify')
                customer = await shopify_handler.create_customer(customer_email, customer_name)
            LOGGER.info(customer)
            gift_card_response = await gift_cards.activate_card(amount_info.get('amount'), amount_info.get('currency'), customer.get('customers', [{}])[0].get('id'))
            body['metadata']['number'] = gift_card_response.get(
                'gift_card', {}).get('id')
            transactions.append({
                'transaction_id': str(uuid4()),
                'refund_amount': -float(amount_info['amount']),
                'instrument_id': financial_instrument_id,
                'reason': 'revoke',
                'payment_method': transaction['payment_method'],
                'currency': transaction['currency'],
                'metadata': body['metadata']
            })
        else:
            LOGGER.info('Process instrument that is pre-revoked already...')
            transactions.append({
                'transaction_id': str(uuid4()),
                'refund_amount': -float(amount_info['amount']),
                'instrument_id': financial_instrument_id,
                'reason': 'revoke',
                'payment_method': transaction['payment_method'],
                'currency': transaction['currency'],
                'metadata': body['metadata']
            })
        revoke_response = transactions
        LOGGER.info(f'Responding with: ${json.dumps(revoke_response)}')
        return {
            'statusCode': 200,
            'body': json.dumps(revoke_response)
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
        LOGGER.exception('Error processing revoke')
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error_code': 'unexpected_error',
                'message': str(ex)
            })
        }


async def _push_captured_revoke_to_shopify(shopify_handler, body, financial_instrument_id, shopify_order_id, shopify_transactions):
    LOGGER.info(f'Processing refund: ${json.dumps(body, indent=4)}')
    try:
        order_id = body['account_id']
        amount_info = body.get('arguments')

        customer_order = await NS_HANDLER.get_customer_order(order_id)
        customer_order = customer_order.get('customer_order', {})
        assert customer_order, 'Customer order not found'

        shopify_order = await shopify_handler.get_order(
            shopify_order_id, 'id,line_items,name,total_price,customer,refunds')
        assert shopify_order, 'Shopify order not found'

        transactions = []
        transaction = next((x for x in body.get(
            'transactions', []) if x.get('reason') == 'capture'), None)
        if not transaction:
            transaction = next((x for x in body.get(
                'transactions', []) if x.get('reason') == 'authorization'), None)
        assert transaction, 'Transaction for refund not found'
        metadata = transaction.get('metadata', {})

        if not is_capture_gift_card(transaction['payment_method']) and shopify_order_id:
            LOGGER.info(
                'Creating a refund of a %s for a shopify created order...' % (transaction['payment_method']))

            if not _check_refund_exists(shopify_transactions, amount_info):
                try:
                    response = await create_refund(
                        shopify_handler,
                        shopify_order_id,
                        customer_order,
                        transaction['payment_method'],
                        amount_info)
                except Exception as ex:
                    LOGGER.error(f'Error: ${str(ex)}')
                    return {
                        'statusCode': 500,
                        'body': json.dumps({
                            'error_code': 'connection_error',
                            'message': 'Refund not created in Shopify. %s' % str(ex)
                        })
                    }
                if response:
                    for transaction_shopify in response['refund']['transactions']:
                        transactions.append({
                            'transaction_id': str(uuid4()),
                            'refund_amount': -float(amount_info.get('amount')),
                            'instrument_id': financial_instrument_id,
                            'reason': 'revoke',
                            'payment_method': transaction['payment_method'],
                            'currency': transaction['currency'],
                            'metadata': body['metadata']
                        })

            else:
                for refund in shopify_order['refunds']:
                    for transaction_shopify in refund['transactions']:
                        transactions.append({
                            'transaction_id': str(uuid4()),
                            'refund_amount': -float(amount_info.get('amount')),
                            'instrument_id': financial_instrument_id,
                            'reason': 'revoke',
                            'payment_method': transaction['payment_method'],
                            'currency': transaction['currency'],
                            'metadata': body['metadata']
                        })

        elif is_capture_gift_card(transaction['payment_method']) and metadata.get('shopify_order_id'):
            LOGGER.info(
                'Creating a refund of a gift card for a shopify created order...')

            if not _check_refund_exists(shopify_transactions, amount_info):
                try:
                    response = await create_refund(
                        shopify_handler,
                        shopify_order_id,
                        customer_order,
                        transaction['payment_method'],
                        amount_info)
                except Exception as ex:
                    LOGGER.error(f'Error: ${str(ex)}')
                    return {
                        'statusCode': 500,
                        'body': json.dumps({
                            'error_code': 'connection_error',
                            'message': 'Refund not created in Shopify. %s' % str(ex)
                        })
                    }

                if response:
                    for transaction_shopify in response['refund']['transactions']:
                        transactions.append({
                            'transaction_id': str(uuid4()),
                            'refund_amount': -float(amount_info.get('amount')),
                            'instrument_id': financial_instrument_id,
                            'reason': 'revoke',
                            'payment_method': transaction['payment_method'],
                            'currency': transaction['currency'],
                            'metadata': body['metadata']
                        })
            else:
                LOGGER.info(
                    'Process instrument that is refunded on Shopify already...')
                transactions.append({
                    'transaction_id': str(uuid4()),
                    'refund_amount': -float(amount_info.get('amount')),
                    'instrument_id': financial_instrument_id,
                    'reason': 'revoke',
                    'payment_method': transaction['payment_method'],
                    'currency': transaction['currency'],
                    'metadata': body['metadata']
                })

        elif is_capture_gift_card(transaction['payment_method']) and metadata.get('order_id'):
            LOGGER.info(
                'Creating a refund of a credit card for a associate created order...')

            assert customer_order.get('consumer', {}).get(
                'email'), 'Could not find email to refund gift card to..'
            customer_email = customer_order.get('consumer', {})['email']
            customer = await shopify_handler.search_customer_by_email(customer_email)
            if len(customer.get('customers', [])) < 1:
                LOGGER.info(
                    'Customer not found, creating it at shopify')
                order_name = customer_order.get('consumer', {}).get('name')
                customer = await shopify_handler.create_customer(customer_email, order_name)
            LOGGER.info(f'Customer: ${customer}')
            gift_card_response = await gift_cards.activate_card(amount_info.get('amount'), amount_info.get('currency'), customer.get('customers', [{}])[0].get('id'))
            body['metadata']['number'] = gift_card_response.get(
                'gift_card', {}).get('id')
            transactions.append({
                'transaction_id': str(uuid4()),
                'refund_amount': -float(gift_card_response['gift_card']['balance']),
                'instrument_id': financial_instrument_id,
                'reason': 'revoke',
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
                'reason': 'revoke',
                'payment_method': transaction['payment_method'],
                'currency': transaction['currency'],
                'metadata': body['metadata']
            })

        refund_response = transactions
        LOGGER.info(f'Responding with: ${json.dumps(refund_response)}')
        return {
            'statusCode': 200,
            'body': json.dumps(refund_response)
        }
    except aiohttp.client_exceptions.ClientConnectorError as ex:
        LOGGER.error(ex, exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error_code': 'connection_error',
                'message': str(ex)
            })
        }
    except Exception as ex:
        LOGGER.error(ex, exc_info=True)
        status_code = 400
        if any(error_msg in str(ex) for error_msg in ERRORS_TO_RETRY):
            status_code = 500
        return {
            'statusCode': status_code,
            'body': json.dumps({
                'error_code': 'unexpected_error',
                'message': str(ex)
            })
        }


async def create_refund(shopify_handler, shopify_order_id, customer_order, payment_method, amount_info):
    json_to_calculate_refund = parse_info_to_calculate_refund(customer_order)
    LOGGER.info(f'Json to calculate refund on Shopify: ${json.dumps(json_to_calculate_refund, indent=4)}')

    calculated_refund_json = await shopify_handler.calculate_refund(
        shopify_order_id, json_to_calculate_refund)

    if calculated_refund_json:
        index = 0
        for i, transaction in enumerate(calculated_refund_json['refund']['transactions']):
            if payment_method != 'credit_card':
                # In case of split payment and full refund of payment
                if float(transaction['amount']) == amount_info.get('amount') and payment_method == transaction['gateway']:
                    index = i
                    break
                # In case of split payment and partial refund of payment
                elif float(transaction['maximum_refundable']) >= amount_info.get('amount') and payment_method == transaction['gateway']:
                    index = i
                    break
            else:
                # In case of split payment and full refund of payment
                if float(transaction['amount']) == amount_info.get('amount') and transaction['gateway'] == 'shopify_payments':
                    index = i
                    break
                # In case of split payment and partial refund of payment
                elif float(transaction['maximum_refundable']) >= amount_info.get('amount') and transaction['gateway'] == 'shopify_payments':
                    index = i
                    break

        transaction_to_refund = calculated_refund_json['refund']['transactions'][index]
        transaction_to_refund['kind'] = 'refund'
        transaction_to_refund['amount'] = str(amount_info.get('amount'))

        json_to_create_refund = calculated_refund_json
        json_to_create_refund['refund']['note'] = 'Newstore originated refund'
        json_to_create_refund['refund']['transactions'] = [
            transaction_to_refund]

        LOGGER.info(f'Json to create refund on Shopify: ${json.dumps(json_to_create_refund, indent=4)}')

        response = await shopify_handler.create_refund(
            order_id=shopify_order_id,
            data=json_to_create_refund
        )
    else:
        LOGGER.error("Couldn't calculate the refund on Shopify")
        return None
    return response


def parse_info_to_calculate_refund(customer_order):
    refund_items = {}
    for item in customer_order['products']:
        if item['status'] == 'canceled':
            external_item_id = _get_extended_attribute(
                item.get('extended_attributes', {}), 'external_item_id')
            if not external_item_id:
                raise Exception("Product %s from order %s does not have \
                    external_item_id extended attribute" % (item['id'], customer_order['sales_order_external_id']))
            if external_item_id in refund_items:
                refund_items[external_item_id] += 1
            else:
                refund_items[external_item_id] = 1

    line_items = []
    for key in refund_items:
        line_items.append({
            "line_item_id": key,
            "quantity": refund_items[key]
        })

    return {
        "refund": {
            "restock": False,
            "shipping": {
                "full_refund": _is_full_refund(customer_order)
            },
            "refund_line_items": line_items
        }
    }


def _is_full_refund(customer_order):
    return customer_order['status'] == 'canceled'


def _check_refund_exists(shopify_transactions, amount_info):
    for transaction in shopify_transactions:
        if transaction['kind'] == 'refund':
            if 'amount' in transaction.get('receipt', {}):
                refund_amount = transaction.get(
                    'receipt', {}).get('amount', 0)/100
            else:
                refund_amount = float(transaction.get('amount', '0.0'))

            if float(refund_amount) == float(amount_info.get('amount')):
                LOGGER.info('Refund already exists on Shopify.')
                return True

    return False


def check_transaction_captured(transactions):
    for transaction in transactions:
        if (transaction['kind'] == 'capture' or transaction['kind'] == 'sale') and transaction['status'] == 'success':
            return True
    return False
