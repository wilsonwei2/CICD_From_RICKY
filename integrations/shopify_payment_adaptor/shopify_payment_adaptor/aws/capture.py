# -*- coding: utf-8 -*-
# Copyright (C) 2020 NewStore, Inc. All rights reserved.
# Author @Aditya Kasturi akasturi@newstore.com
import logging
import json
import asyncio
import aiohttp

from uuid import uuid4

from shopify_payment_adaptor.utils.utils import is_capture_credit_card, is_capture_gift_card, get_newstore_handler, get_shopify_handler


LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
NS_HANDLER = get_newstore_handler()


def handler(event, context):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(
        _push_capture_to_shopify(
            body=json.loads(event['body']),
            financial_instrument_id=event['pathParameters']['financial_instrument_id']
        )
    )
    loop.stop()
    loop.close()
    return result


async def _push_capture_to_shopify(body, financial_instrument_id):
    try:
        amount_info = body.get('arguments')
        LOGGER.info(f'Processing capture: {json.dumps(body, indent=4)}')
        transactions = []
        transaction = next((x for x in body.get(
            'transactions', []) if x.get('reason') == 'authorization'), None)
        assert transaction, 'Transaction for capture not found'
        metadata = body.get('metadata', {})
        metadata_transaction = transaction.get('metadata', {})
        metadata.update(metadata_transaction)

        shopify_handler = get_shopify_handler(amount_info.get('currency'))
        if is_capture_credit_card(transaction['payment_method']) and metadata.get('shopify_order_id'):
            shopify_order_id = metadata['shopify_order_id']
            shopify_order = await shopify_handler.get_order(shopify_order_id, params='id,line_items,name,total_price,financial_status')
            transaction_id = metadata.get('transaction_id')
            amount = None

            LOGGER.info(f'Shopify Order: {json.dumps(shopify_order, indent=4)}')

            if transaction_id:
                shopify_transaction = await shopify_handler.get_transaction(shopify_order_id, transaction_id)
                if shopify_transaction.get('kind') == 'sale' and shopify_transaction.get('status') == 'success':
                    LOGGER.info('Sale transaction, already captured')
                    amount = shopify_transaction['amount']
                elif shopify_transaction.get('kind') == 'authorization':
                    LOGGER.info('Auth/Capture transaction, Validating if already captured')
                    shopify_transactions = await shopify_handler.get_transactions_for_order(shopify_order_id)
                    captured_transaction = _validate_transaction_was_captured(shopify_transactions, transaction_id)
                    if captured_transaction:
                        LOGGER.info(f'Found already captured transactions: {json.dumps(captured_transaction)}')
                        amount = captured_transaction['amount']
            if not amount:
                if shopify_order.get('financial_status') not in ['pending', 'authorized', 'partially_paid', None, '']:
                    amount = amount_info.get('amount')
            if amount:
                LOGGER.info(
                    'Process instrument that is pre-captured already...')
                transactions.append({
                    'transaction_id': str(uuid4()),
                    'capture_amount': -float(amount),
                    'refund_amount': float(amount),
                    'instrument_id': financial_instrument_id,
                    'reason': 'capture',
                    'payment_method': transaction['payment_method'],
                    'currency': amount_info.get('currency'),
                    'metadata': metadata
                })
            else:
                LOGGER.info('Processing shopify order credit card capture..')
                LOGGER.info('Creating transaction at shopify....')
                try:
                    transaction_rsp = await _create_capture_transaction(
                        shopify_order_id,
                        transaction['capture_amount'],
                        shopify_handler
                    )
                    metadata['shopify_auth_id'] = transaction_rsp.get('transaction', {}).get('parent_id')
                    metadata['shopify_capture_id'] = transaction_rsp.get('transaction', {}).get('id')
                    transactions.append({
                        'transaction_id': str(uuid4()),
                        'capture_amount': -float(transaction_rsp['transaction']['amount']),
                        'refund_amount': float(transaction_rsp['transaction']['amount']),
                        'instrument_id': financial_instrument_id,
                        'reason': 'capture',
                        'payment_method': transaction['payment_method'],
                        'currency': amount_info.get('currency'),
                        'metadata': metadata
                    })
                except Exception as ex:
                    if 'No capturable transaction was found' in str(ex):
                        transactions.append({
                            'transaction_id': str(uuid4()),
                            'capture_amount': -float(amount_info.get('amount')),
                            'refund_amount': float(amount_info.get('amount')),
                            'instrument_id': financial_instrument_id,
                            'reason': 'capture',
                            'payment_method': transaction['payment_method'],
                            'currency': transaction['currency'],
                            'metadata': metadata
                        })
                    else:
                        raise ex

        elif is_capture_gift_card(transaction['payment_method']) and metadata.get('order_id'):
            LOGGER.info(
                'Process gift card instrument that was captured during authorization...')
            transactions.append({
                'transaction_id': str(uuid4()),
                'capture_amount': -float(amount_info.get('amount')),
                'refund_amount': float(amount_info.get('amount')),
                'instrument_id': financial_instrument_id,
                'reason': 'capture',
                'payment_method': transaction['payment_method'],
                'currency': amount_info.get('currency'),
                'metadata': metadata
            })
        else:
            LOGGER.info('Process instrument that is pre-captured already...')
            transactions.append({
                'transaction_id': str(uuid4()),
                'capture_amount': -float(amount_info.get('amount')),
                'refund_amount': float(amount_info.get('amount')),
                'instrument_id': financial_instrument_id,
                'reason': 'capture',
                'payment_method': transaction['payment_method'],
                'currency': amount_info.get('currency'),
                'metadata': metadata
            })
        capture_response = transactions
        LOGGER.info(f'Responding with: {json.dumps(capture_response)}')
        return {
            'statusCode': 200,
            'body': json.dumps(capture_response)
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
        LOGGER.exception('Error processing capture')
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error_code': 'unexpected_error',
                'message': str(ex)
            })
        }


async def _create_capture_transaction(shopify_order_id, amount, shopify_handler):
    try:
        data_transaction = {
            'transaction': {
                'amount': str(amount),
                'kind': 'capture'
            }
        }
        transaction_rsp = await shopify_handler.create_transaction(
            order_id=shopify_order_id,
            data=data_transaction
        )
        return transaction_rsp
    except Exception:
        raise


def _get_shipped_items(shipped_items: dict, order_items: list) -> dict:
    return [item for item in order_items if any(item['sku'] == ship_item['product_sku'] for ship_item in shipped_items)]


def _validate_transaction_was_captured(transactions: list, transaction_id: str) -> dict:
    """
    Args:
        transactions: Array containing a list of transactions in shopify
        transaction_id: String with original transaction authorization
    Returns:
        dict -> Dict containing the captured transaction with a sucesfull state, None will be returned if nothing is found
    """
    transactions_with_parent_id = [transaction for transaction in transactions if str(transaction.get('parent_id')) == str(transaction_id)]
    for transaction in transactions_with_parent_id:
        if transaction.get('status') == 'success':
            return transaction
    return None
