import json
import os
import logging
from param_store.client import ParamStore
from newstore_adapter.connector import NewStoreConnector

TRUE_VALUES = ['1', 'yes', 'true', 1, True]
TENANT = os.environ.get('TENANT') or 'frankandoak'
STAGE = os.environ.get('STAGE') or 'x'
PARAM_STORE = None
NEWSTORE_CONN = None
LOGGER = logging.getLogger()


def set_logger_level(logger):
    log_level = os.environ.get('LOG_LEVEL', 'info').upper()
    log_level_number = getattr(logging, log_level, None)
    if not isinstance(log_level_number, int):
        LOGGER.info('LOG_LEVEL passed is invalid, default to INFO.')
        log_level_number = getattr(logging, 'INFO', None)
    logger.setLevel(log_level_number)


set_logger_level(LOGGER)


def get_param_store():
    global PARAM_STORE  # pylint: disable=global-statement
    if not PARAM_STORE:
        PARAM_STORE = ParamStore(TENANT, STAGE)
    return PARAM_STORE


def get_newstore_conn(context, raise_errors=True):
    global NEWSTORE_CONN  # pylint: disable=global-statement
    if not NEWSTORE_CONN:
        NEWSTORE_CONN = NewStoreConnector(
            tenant=TENANT,
            context=context,
            host=get_newstore_creds()['host'],
            username=get_newstore_creds()['username'],
            password=get_newstore_creds()['password'],
            raise_errors=raise_errors
        )
    return NEWSTORE_CONN


def get_param(param_path):
    return json.loads(get_param_store().get_param(param_path))


def get_newstore_creds():
    return json.loads(get_param_store().get_param('newstore'))


def get_ext_order(ns_conn, order_id):
    ext_order = ns_conn.get_external_order(order_id.replace('#', '%23'))
    assert ext_order, f"External order not fetched from NewStore for order {order_id}"
    LOGGER.debug(f'External order: {json.dumps(ext_order, indent=4)}')
    return ext_order


def get_customer_order(ns_conn, order_uuid):
    customer_order = ns_conn.get_customer_order(order_uuid)
    assert customer_order, f"Customer order not fetched from NewStore for order {order_uuid}"
    LOGGER.debug(f'Customer order: {json.dumps(customer_order, indent=4)}')
    return customer_order
