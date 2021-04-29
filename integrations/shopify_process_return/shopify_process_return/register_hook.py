import os
import logging
import json
from utils import get_all_shopify_handlers

EVENT_NAME = 'shopify_event_name'

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def handler(event, context):
    """
    Start of the lambda handler
    :param event: Shopify register webhook return json
    :param context: function context
    """
    shopify_handlers = get_all_shopify_handlers()
    url = os.environ.get('process_return_url')
    # Loop through each Shopify instance, fetch orders from it, and create them in NwS.
    for shopify_handler in shopify_handlers:
        channel = shopify_handler['config']['channel']
        handler = shopify_handler['handler']
        channel_url = f'{url}?channel={channel}'
        LOGGER.info(f'Validate if hook for return exists: {channel_url}...')
        if not _validate_hook_already_exists(channel_url, handler):
            LOGGER.info('Webhook for returns does not exist, registering it...')
            _create_refund_hook(channel_url, handler)
        else:
            LOGGER.info('Webhook already exists, nothing more to do....')
    return 'Completed'


def _validate_hook_already_exists(url, handler):
    LOGGER.info('Getting hook for url %s', url)
    hook_response = handler._get_hook_by_url(url)
    if len(hook_response) > 0:
        return True
    else:
        False


def _create_refund_hook(callback_url, handler, event=os.environ.get(EVENT_NAME, 'refunds/create')):
    LOGGER.info('Creating webhook for %s at Shopify', callback_url)
    handler._create_hook(callback_url, event)


