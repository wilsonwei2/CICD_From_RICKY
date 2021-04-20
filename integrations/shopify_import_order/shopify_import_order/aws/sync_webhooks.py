import os
import logging
from shopify_import_order.handlers.utils import Utils

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
EVENTS = os.environ.get('EVENT_TYPE', 'orders/updated').split(',')


def handler(event, context): # pylint: disable=W0613
    """
    Start of the lambda handler
    :param event: Shopify register webhook return json
    :param context: function context
    """
    url = os.environ.get('ORDER_IMPORT_API')
    import_url = f'{url}/d/import/shopify/order'
    shopify_handler = Utils.get_instance().get_shopify_handler()
    # Loop through each Shopify instance, fetch orders from it, and create them in NwS.
    for event_type in EVENTS:
        if not _validate_hook_already_exists(import_url, shopify_handler, event_type):
            LOGGER.info(f'Webhook for {event_type} does not exist, registering it...')
            _create_order_hook(callback_url=import_url, shopify_handler=shopify_handler, event=event_type)
        else:
            LOGGER.info('Webhook already exists, nothing more to do....')

    return True


def _validate_hook_already_exists(url, shopify_handler, event):
    LOGGER.info(f'Getting hook for url {url}')
    hook_response = shopify_handler.get_hook_by_url(url, topic=event)
    if len(hook_response) > 0 and hook_response[0].get('topic', '').lower() == event.lower():
        return True
    return False


def _create_order_hook(callback_url, shopify_handler, event):
    LOGGER.info(f'Creating webhook for {event} at Shopify')
    shopify_handler.create_hook(callback_url, event)
