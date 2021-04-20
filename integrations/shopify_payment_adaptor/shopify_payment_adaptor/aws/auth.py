import logging
import asyncio
import json
import aiohttp

from shopify_payment_adaptor.aws.gift_cards import adjust_gift_card

from uuid import uuid4

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

def is_capture_gift_card(payment_method: str) -> bool:
    return payment_method == 'gift_card'

def handler(event, context):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(
        authorization(body=json.loads(event['body'])))
    loop.stop()
    loop.close()
    return result


async def authorization(body):
    """
    The authorization handler, just returns a parsed 200 response.
    The order is already authorised at shopify
    """
    try:
        LOGGER.info('Requesting with authotrization: {auth}'.format(
            auth=json.dumps(body, indent=4)))
        transactions = []
        amount_info = body.get('arguments')
        if is_capture_gift_card(body['arguments']['payment_method']) and body['metadata'].get('order_id'):
            LOGGER.info('Processing associate order with gift card capture...')
            card_number = body['metadata'].get('number')
            if card_number.startswith('shopify-giftcard-v1-'):
                card_number = card_number[20:]
            gift_card_response = await adjust_gift_card(card_number, 0.0 - float(amount_info.get('amount')),
                                                        'Capturing gift card', amount_info.get('currency'))
            transactions.append({
                'transaction_id': str(uuid4()),
                'capture_amount': -float(gift_card_response['adjustment']['amount']),
                'refund_amount': 0,
                'instrument_id': str(uuid4()),
                'reason': 'authorization',
                'payment_method': body['arguments']['payment_method'],
                'currency': amount_info.get('currency'),
                'metadata': {**body['metadata']}
            })
        else:
            transactions.append({
                'transaction_id': str(uuid4()),
                'instrument_id': str(uuid4()),
                'capture_amount': body['arguments']['amount'],
                'refund_amount': 0,
                'currency': body['arguments']['currency'],
                'reason': 'authorization',
                'payment_method': body['arguments']['payment_method'],
                'metadata': body['metadata']
            })
        LOGGER.info('Responding with authorization: {auth}'.format(
            auth=json.dumps(transactions, indent=4)))

        return {
            'statusCode': 200,
            'body': json.dumps(transactions)
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
        LOGGER.exception('Error processing Authorization')
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error_code': 'unexpected_error',
                'message': str(ex)
            })
        }
