import logging
import os
import json

from historical_orders_adapter.custom_exceptions import NotSupportedNewStoreWebHookException
from historical_orders_adapter.payment_connector import PaymentConnector


LOG_LEVEL = int(os.environ.get("LOG_LEVEL", "10"))
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOG_LEVEL)


def handle(event, _):
    LOGGER.info(event)
    event_body = json.loads(event['body'])
    LOGGER.info(f'handler.handle: Handle Payment event: {event}')
    LOGGER.info(f'handler.handle: Handle Payment body: {event_body}')
    body = []

    if event['path'] == '/financial_instruments':
        body = handle_authorization(event_body)

    elif '_capture' in event['path']:
        body = handle_capture(event_body)

    elif '_refund' in event['path']:
        body = handle_refund(event_body)

    elif '_revoke' in event['path']:
        body = handle_revoke(event_body)

    else:
        LOGGER.info(f'Path: %s', event['path'])
        raise NotSupportedNewStoreWebHookException(path=event['path'])

    LOGGER.info(f'handler.handle: Response: {json.dumps(body)}')
    return {
        "statusCode": 200,
        "body": json.dumps(body),
        "headers": {
            "Content-Type": "application/json"
        }
    }


def handle_authorization(event_body):
    LOGGER.info('Handle Authorization')
    payment_data = PaymentConnector().perform_authorization(event_body)
    return [{
        "payment_method": "historical_payment",
        "payment_wallet": "historical_payment",
        "transaction_id": payment_data['transaction_id'],
        "instrument_id": payment_data['instrument_id'],
        "capture_amount": payment_data['capture_amount'],
        "refund_amount": 0,
        "currency": payment_data['currency'],
        "metadata": {
            "essential": {
                "instrument_metadata": {
                    "card_brand": "Visa",
                    "card_last4": "0",
                    "card_expiration_month": 11,
                    "card_expiration_year": 2030,
                    "payer_email": "matias.sanchez@positiveminds.io"
                }
            }
        },
        "reason": "authorization",
        "created_at": payment_data['created_at'],
        "processed_at": payment_data['processed_at']
    }]


def handle_capture(event_body):
    LOGGER.info('Handle Capture')
    payment_data = PaymentConnector().perform_capture(event_body)

    return [
        {
            "payment_method": "historical_payment",
            "payment_wallet": "historical_payment",
            "transaction_id": payment_data['transaction_id'],
            "instrument_id": payment_data['instrument_id'],
            "capture_amount": payment_data['capture_amount'],
            "refund_amount": payment_data['refund_amount'],
            "currency": payment_data['currency'],
            "created_at": payment_data['created_at'],
            "processed_at": payment_data['processed_at'],
            "reason": "capture"
        }
    ]


def handle_refund(event_body):
    # Check in case of multiple trasactions, since the order may have been captured and we need to refund in PSP
    LOGGER.info('Handle Refund')
    payment_data = PaymentConnector().perform_refund(event_body)

    return [
        {
            "payment_method": "historical_payment",
            "payment_wallet": "historical_payment",
            "transaction_id": payment_data['transaction_id'],
            "instrument_id": payment_data['instrument_id'],
            "capture_amount": 0,
            "refund_amount": payment_data['refund_amount'],
            "currency": payment_data['currency'],
            "created_at": payment_data['created_at'],
            "processed_at": payment_data['processed_at'],
            "reason": "refund"
        }
    ]


def handle_revoke(event_body):
    # Check in case of multiple trasactions, since the order may have been captured and we need to refund in PSP
    LOGGER.info('Handle Revoke')
    payment_data = PaymentConnector().perform_revoke(event_body)

    return [
        {
            "payment_method": "historical_payment",
            "payment_wallet": "historical_payment",
            "transaction_id": payment_data['transaction_id'],
            "instrument_id": payment_data['instrument_id'],
            "capture_amount": payment_data['capture_amount'],
            "refund_amount": 0,
            "currency": payment_data['currency'],
            "created_at": payment_data['created_at'],
            "processed_at": payment_data['processed_at'],
            "reason": "revoke"
        }
    ]
