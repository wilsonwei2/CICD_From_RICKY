import os
import json
import logging
from lambda_utils.sqs.SqsHandler import SqsHandler
from .shopify.verify_webhook import verify_webhook
from .utils import get_shopify_config


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

SQS_HANDLER = SqsHandler(os.environ['sqs_returns_name'])

def handler(event, context): # pylint: disable=unused-argument
    """
    Start of the lambda handler
    :param event: Shopify webhook order json
    :param context: function context
    """
    body = event.get('body')
    LOGGER.info(f'Received refund event: {body}')
    result = _save_refund(event)
    if result:
        return {
            "statusCode": 200
        }
    return {
        "statusCode": 500
    }


def _save_refund(event):
    the_handler = get_shopify_config()

    if not _verify_webhook(event=event, secret=the_handler['shopify_app_secret']):
        return False
    _drop_to_queue(event['body'])
    return True


def _drop_to_queue(message):
    message = json.loads(message)
    SQS_HANDLER.push_message(message=json.dumps(message))

def _verify_webhook(event, secret):
    hmac = event['headers'].get('X-Shopify-Hmac-Sha256')
    body = event['body'][:30]
    LOGGER.info(f'Verify message: {body} with secret: {secret[:10]} and hmac: {hmac}')
    if not hmac or not verify_webhook(event['body'], hmac, secret):
        LOGGER.error(f'Validation of Hmac doesn\'t match. [hmac={hmac}]')
        return False
    return True
