import os
import logging
from .utils import get_all_shopify_handlers

EVENT_NAME = 'shopify_event_name'

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def handler(event, context): # pylint: disable=unused-argument
    """
    Start of the lambda handler
    :param event: Shopify register webhook return json
    :param context: function context
    """
    shopify_handlers = get_all_shopify_handlers()
    url = os.environ.get('PROCESS_RETURN_URL')
    return_url = f'{url}/d/shopify/process/return'

    # Loop through each Shopify instance, fetch orders from it, and create them in NwS.
    for shopify_handler in shopify_handlers:
        channel = shopify_handler['config']['channel']
        the_handler = shopify_handler['handler']
        channel_url = f'{return_url}?channel={channel}'
        LOGGER.info(f'Validate if hook for return exists: {channel_url}...')
        if not _validate_hook_already_exists(channel_url, the_handler):
            LOGGER.info('Webhook for returns does not exist, registering it...')
            _create_refund_hook(channel_url, the_handler)
        else:
            LOGGER.info('Webhook already exists, nothing more to do....')
    return 'Completed'


def _validate_hook_already_exists(url, the_handler):
    LOGGER.info(f'Getting hook for url {url}')
    hook_response = the_handler._get_hook_by_url(url) # pylint: disable=protected-access
    return len(hook_response) > 0


def _create_refund_hook(callback_url, the_handler, event=os.environ.get(EVENT_NAME, 'refunds/create')):
    LOGGER.info(f'Creating webhook for {callback_url} at Shopify')
    the_handler._create_hook(callback_url, event) # pylint: disable=protected-access
