import logging
import os
import requests
import hashlib
import base64
import hmac
import time
import datetime
import simplejson as json
from shopify_import_order.handlers.utils import Utils

IMPORT_ORDER_ENDPOINT = os.environ.get('ORDER_IMPORT_API') + '/d/process/shopify/order'
RETRIEVE_ORDERS_FROM_HOURS = int(os.environ.get('HOURS_TO_CHECK', '1'))
NS_HANDLER = Utils.get_instance().get_ns_handler()
SHOPIFY_HANDLER = Utils.get_instance().get_shopify_handler()
LIMIT = 250
LOGGER = logging.getLogger(__name__)
LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER.setLevel(LOG_LEVEL)


def handler(event, context): # pylint: disable=W0613
    """Sync Newstore orders with Shopify.

    Fetch configs for multiple Shopify instances, loop through each, fetch
    orders within date range, and create those orders in Newstore.

    Args:
        event: Triggered by Cloudwatch timer.
        context: Lambda context.

    Returns:
        nothing
    """
    LOGGER.info('INSIDE SYNC')

    end_date = None
    start_date = None

    shopify_config = json.loads(Utils.get_instance().get_parameter_store().get_param('shopify'))
    secret = shopify_config['shared_secret']

    # If event is CloudWatch it means that it should use the HOURS_TO_CHECK
    # Else it's from API Gateway so it should have the start_date and end_date on payload
    if event.get('detail-type', '') == 'Scheduled Event':
        LOGGER.info("Event is Scheduled CloudWatch. Process it with HOURS_TO_CHECK.")
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(hours=RETRIEVE_ORDERS_FROM_HOURS)
        starts_at = start_date.strftime('%Y-%m-%dT%H:00:00Z')
        ends_at = end_date.strftime('%Y-%m-%dT%H:00:00Z')
    else:
        body = json.loads(event.get('body', '{}'))
        LOGGER.info(f"Getting API call with: \n{json.dumps(body, indent=4)}")

        # In case a timeframe is received
        if set(['end_date', 'start_date']).issubset(body):
            LOGGER.info('Timeframe received.')
            starts_at = body.get('start_date')
            ends_at = body.get('end_date')
        # In case a list of shopify order ids is received
        elif 'order_list' in body:
            LOGGER.info('Order list received.')
            shopify_order_list = body['order_list']
        # If neither timeframe nor order list is provided, utilize the default behavior
        else:
            LOGGER.info("Neither timeframe nor order list was provided. Utilizing default timeframe")
            end_date = datetime.datetime.now()
            start_date = end_date - datetime.timedelta(hours=RETRIEVE_ORDERS_FROM_HOURS)
            starts_at = start_date.strftime('%Y-%m-%dT%H:00:00Z')
            ends_at = end_date.strftime('%Y-%m-%dT%H:00:00Z')

    if start_date and end_date:
        LOGGER.info(f'Getting orders between {starts_at} and {ends_at}')
        last_shopify_orders = SHOPIFY_HANDLER.get_orders(
            starts_at=starts_at,
            ends_at=ends_at,
            params=None,
            limit=LIMIT
        )
    else:
        LOGGER.info(f'Getting orders in list {shopify_order_list}.')
        last_shopify_orders = SHOPIFY_HANDLER.get_orders(
            limit=LIMIT,
            starts_at=None,
            ends_at=None,
            params=None,
            ids=shopify_order_list
        )

    LOGGER.info(f'Found {len(last_shopify_orders)} to process.')

    for order in last_shopify_orders:
        LOGGER.info(f'Processing order with Shopify name: {order["name"]}')
        order_number = order['name'].replace('#', '')
        order_name = f'{order_number}'
        if not validate_order_exists(order_name):
            try:
                LOGGER.info('creating order')
                response = create_order(order, secret)
                LOGGER.debug(json.dumps(response))
            except Exception:
                LOGGER.exception('Failed to create order')
        else:
            LOGGER.info(f'Order already processed: {order["name"]}')


def rate_limited(max_per_second):
    min_interval = 1.0 / float(max_per_second)
    def decorate(func):
        last_time_called = [0.0]
        def rate_limited_function(*args, **kargs):
            elapsed = time.clock() - last_time_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args, **kargs)
            last_time_called[0] = time.clock()
            return ret
        return rate_limited_function
    return decorate


def validate_order_exists(order_id):
    try:
        NS_HANDLER.get_order_by_external_id(order_id)
        return True
    except Exception:
        LOGGER.info('Failed to find this order')
        LOGGER.warning('Failed to find this order and will create it on NewStore')
        return False


@rate_limited(0.5)
def create_order(order, secret):
    headers = {
        'X-Shopify-Order-Id': str(order['id']),
        'X-Shopify-Hmac-Sha256': calculate_hmac(json.dumps(order), secret)
    }

    response = requests.post(IMPORT_ORDER_ENDPOINT,
                             data=json.dumps(order), headers=headers)
    response.raise_for_status()
    created_order = response.json()
    LOGGER.debug(json.dumps(created_order))
    return created_order


def calculate_hmac(data, secret):
    hash_hmac = hmac.new(str.encode(secret), str.encode(data), hashlib.sha256)
    return base64.b64encode(hash_hmac.digest()).decode()
