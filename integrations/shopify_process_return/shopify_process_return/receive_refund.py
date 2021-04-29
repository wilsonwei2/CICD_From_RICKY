import os
import re
import json
import logging
from lambda_utils.sqs.SqsHandler import SqsHandler
from shopify.verify_webhook import verify_webhook
from utils import get_shopify_config


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

SQS_HANDLER = SqsHandler(os.environ['sqs_returns_name'])

def handler(event, context):
    """
    Start of the lambda handler
    :param event: Shopify webhook order json
    :param context: function context
    """
    LOGGER.info('Received refund event: %s', event.get('body'))
    result = _save_refund(event)
    if result:
        return {
            "statusCode": 200
        }
    else:
        return {
            "statusCode": 500
        }


def _save_refund(event):
    handler = get_shopify_config()
    
    if not _verify_webhook(event=event, secret=handler['shopify_app_secret']):
        return False
    else:
        _drop_to_queue(event['body'])
        return True


def _drop_to_queue(message):
    message = json.loads(message)
    SQS_HANDLER.push_message(message=json.dumps(message))

def _verify_webhook(event, secret):
    hmac = event['headers'].get('X-Shopify-Hmac-Sha256')
    LOGGER.info('Verify message: %s with secret: %s and hmac: %s ', event['body'][:30], secret[:10], hmac)
    if not hmac or not verify_webhook(event['body'], hmac, secret):
        LOGGER.error('Validation of Hmac doesn\'t match. [hmac=%s]', hmac)
        return False
    return True