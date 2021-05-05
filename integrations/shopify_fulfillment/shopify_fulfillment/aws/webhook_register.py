import os
import logging
import asyncio
from shopify_fulfillment.helpers.utils import Utils

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
WEBHOOK_EVENT_FILTER = [
    event.strip()
    for event in os.environ.get('WEBHOOK_EVENT_FILTER', 'fulfillment_request.items_completed').split(',')
]
WEBHOOK_NAME = os.environ.get('WEBHOOK_NAME', 'frankandoak-sf-events-to-sqs')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')


def handler(_, context):
    """
    Arguments:
        event {dic} -- Lambda event
        context {object} -- Lambda object

    Returns:
        string -- Result string of process
    """
    Utils.get_newstore_conn(context)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_validate_webhook())
    loop.stop()
    loop.close()
    return result


async def _validate_webhook() -> str:
    """
    Start of the lambda handler
    :param event: Shopify register webhook return json
    :param context: function context
    """

    LOGGER.info('Validate if hook for events exists...')
    if not WEBHOOK_URL:
        LOGGER.warning('Can not find the webhook url')
        return 'Can not find the webhook url'
    LOGGER.info(f'Getting hook for url {WEBHOOK_URL}')
    try:
        hook_response = Utils.get_newstore_conn().get_integration(WEBHOOK_NAME)
        LOGGER.info(hook_response)
        if not _validate_hook_is_active(hook_response):
            await _restart_refund_hook()
        else:
            LOGGER.info('Webhook already exists, nothing more to do....')
    except Exception as ex:
        if 'resource_not_found' in str(ex):
            LOGGER.error('Webhook for events does not exist, creating it...')
            await _create_refund_hook(WEBHOOK_URL)
        else:
            LOGGER.error(str(ex))
    return 'Completed'


def _validate_hook_is_active(hook: dict) -> bool:
    return hook['status'] == 'running'


async def _create_refund_hook(callback_url, name=WEBHOOK_NAME):
    LOGGER.info(f'Creating webhook for {callback_url} at Newstore')
    filters = {
        "event_filter": WEBHOOK_EVENT_FILTER,
        "entity_filter": []
    }
    return Utils.get_newstore_conn().create_integration(name, callback_url, filters)


async def _restart_refund_hook(name=WEBHOOK_NAME):
    LOGGER.info(f'Starting webhook for {name} at Newstore')
    return Utils.get_newstore_conn().start_integration(name)
