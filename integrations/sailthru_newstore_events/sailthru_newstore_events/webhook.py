import os
import logging
from newstore_common.aws import init_root_logger
from newstore_adapter.connector import NewStoreConnector
from newstore_adapter.exceptions import NewStoreAdapterException

init_root_logger(__name__)
LOGGER = logging.getLogger(__name__)

SAILTHRU_HOOK_NAME = os.environ.get('SAILTHRU_HOOK_NAME')
TENANT = os.environ.get('TENANT')


def handler(event, context): # pylint: disable=unused-argument
    """
    Arguments:
        event {dic} -- Lambda event
        context {object} -- Lambda object

    Returns:
        string -- Result string of process
    """
    result = _validate_webhook(context)
    return result


def _validate_webhook(context):
    LOGGER.info('Validate if hook for events exists...')

    url = os.environ.get('SAILTHRU_AWSAPI_URL')
    filter_events = os.environ.get('EVENTS_TO_FILTER', '').split(',')

    filter_conditions = {
        'event_filter': filter_events
    }

    ns_handler = NewStoreConnector(
        tenant=TENANT,
        context=context
    )

    try:
        hook_response = ns_handler.get_integration(SAILTHRU_HOOK_NAME)
        LOGGER.debug(f'hook response {hook_response}')

        if not _validate_callback_url(hook_response, url):
            hook_response = _update_hook(ns_handler, hook_response, url)
            LOGGER.info(f'Webhook updated: {hook_response}')

        if not _validate_hook_is_active(hook_response):
            _restart_hook(ns_handler)
        else:
            LOGGER.info('Webhook already exists, nothing more to do....')

    except NewStoreAdapterException as exc:
        if 'resource_not_found' in str(exc):
            LOGGER.info('Webhook for events does not exist, creating it...')
            _create_fulfilment_hook(ns_handler, url, filter_conditions)
        else:
            LOGGER.error(str(exc))
    except Exception: # pylint: disable=broad-except
        LOGGER.exception('Something failed when fetching info')

    return 'Completed'


def _validate_callback_url(hook: dict, callback_url: str) -> bool:
    return hook['callback_parameters']['callback_url'] == callback_url


def _validate_hook_is_active(hook: dict) -> bool:
    return hook['status'] == 'running'


def _update_hook(newstore_handler, hook: dict, callback_url):
    while hook['status'] == 'running':
        hook = newstore_handler.stop_integration(hook['id'])
    return newstore_handler.update_integration(hook['id'], callback_url)


def _create_fulfilment_hook(newstore_handler, callback_url, filter_events, name=SAILTHRU_HOOK_NAME):
    LOGGER.info(f'Creating webhook {name} with callback {callback_url}')
    return newstore_handler.create_integration(name, callback_url, filter_events)


def _restart_hook(newstore_handler, name=SAILTHRU_HOOK_NAME):
    LOGGER.info(f'Starting webhook {name}')
    return newstore_handler.start_integration(name)
