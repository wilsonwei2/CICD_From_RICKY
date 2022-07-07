import os
import logging
import json
from lambda_utils.sqs.SqsHandler import SqsHandler
from yotpo_shopper_loyalty.handlers.utils import Utils
from yotpo_shopper_loyalty.handlers.yotpo_handler import YotpoHandler

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

SQS_HANDLER = SqsHandler(os.environ['SQS_YOTPO_ORDER_OPENED'])

NEWSTORE_HANDLER = None

def handler(event, context):  # pylint: disable=unused-argument
    """
    Start of the lambda handler
    :param event: Shopify webhook order json
    :param context: function context
    """
    LOGGER.info(f'Processing return Event: {event}')
    utils = Utils.get_instance()
    global NEWSTORE_HANDLER  # pylint: disable=W0603
    NEWSTORE_HANDLER = utils.get_ns_handler()

    for record in event.get('Records', []):
        try:
            response_bool = _process_order(record['body'])
            if response_bool:
                LOGGER.info('Event processed, deleting message from queue...')
                SQS_HANDLER.delete_message(record['receiptHandle'])
            else:
                LOGGER.error(f'Failed to process event: {record["body"]}')
        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.exception('Some error happen while processing the return')
            err_msg = str(ex)
            LOGGER.error(f'Error message: {err_msg}')
            continue

def _process_order(order_json):
    """
    Process the order json
    :param order_json: Shopify webhook order json
    :return: True if the order was processed successfully, False otherwise
    """
    LOGGER.info(f'Processing order: {order_json}')
    order_payload = json.loads(order_json).get('payload', {})
    if (order_payload.get('channel_type')) == 'web':
        _disable_ns_coupons(order_payload)
    elif (order_payload.get('channel_type')) == 'store':
        _disable_shopify_coupons(order_payload)
        _create_yotpo_order(order_payload)
    return False

def _disable_ns_coupons(order_payload):
    discounts = order_payload.get('discounts', [])
    coupons = list([discount.get('coupon_code') for discount in discounts
                    if (discount.get('coupon_code').startswith("FAOU") or discount.get('coupon_code').startswith("FAOC"))])
    LOGGER.info(f'Disabling coupons: {coupons}')
    coupon_items_to_disable = NEWSTORE_HANDLER.get_coupons(coupons)
    LOGGER.info(f'Get Coupons response: {coupon_items_to_disable}')
    coupon_ids_to_disable = [coupon_item.get('id') for coupon_item in coupon_items_to_disable]
    LOGGER.info(f'Disabling coupons: {coupon_ids_to_disable}')
    for coupon_id in coupon_ids_to_disable:
        NEWSTORE_HANDLER.disable_coupon(coupon_id)
        LOGGER.info(f'Disabled coupon: {coupon_id}')


def _disable_shopify_coupons(order_payload): # pylint: disable=W0613
    pass

def _create_yotpo_order(order_payload):
    LOGGER.info(f'Creating yotpo order: {order_payload}')
    yotpo_handler = YotpoHandler()
    return yotpo_handler.create_order(order_payload)
