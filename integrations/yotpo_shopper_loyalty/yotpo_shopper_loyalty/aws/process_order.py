import os
import logging
import json
from lambda_utils.sqs.SqsHandler import SqsHandler
from requests import HTTPError
from yotpo_shopper_loyalty.handlers.utils import Utils
from yotpo_shopper_loyalty.handlers.yotpo_handler import YotpoHandler
from yotpo_shopper_loyalty.handlers.shopify_gql import ShopifyDiscountCodeGQL

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

SQS_HANDLER = SqsHandler(os.environ['SQS_YOTPO_ORDER_OPENED'])

NEWSTORE_HANDLER = None

def handler(event, context):  # pylint: disable=unused-argument
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
            LOGGER.exception('Some error occurred while processing the order w.r.t Yotpo')
            err_msg = str(ex)
            LOGGER.error(f'Error message: {err_msg}')
            continue

def _process_order(order_json):
    LOGGER.info(f'Processing order: {order_json}')
    order_payload = json.loads(order_json).get('payload', {})
    discounts = order_payload.get('discounts', [])
    coupon_codes = list([discount.get('coupon_code') for discount in discounts
                         if (discount.get('coupon_code').startswith("FAOU") or discount.get('coupon_code').startswith("FAOC"))])
    if (order_payload.get('channel_type')) == 'web':
        return _disable_ns_coupons(coupon_codes)
    elif (order_payload.get('channel_type')) == 'store':
        if _disable_shopify_coupons(coupon_codes) and _create_yotpo_order(order_payload):
            return True
    return False

def _disable_ns_coupons(coupon_codes):
    if not coupon_codes:
        LOGGER.info('No coupons to disable on Newstore')
        return True
    try:
        LOGGER.info(f'Disabling coupons: {coupon_codes}')
        coupon_items_to_disable = NEWSTORE_HANDLER.get_coupons(coupon_codes)
        LOGGER.info(f'Get Coupons response: {coupon_items_to_disable}')
        coupon_ids_to_disable = [coupon_item.get('id') for coupon_item in coupon_items_to_disable]
        LOGGER.info(f'Disabling coupons: {coupon_ids_to_disable}')
        for coupon_id in coupon_ids_to_disable:
            NEWSTORE_HANDLER.disable_coupon(coupon_id)
            LOGGER.info(f'Disabled coupon: {coupon_id}')
        return True
    except HTTPError as exc:
        LOGGER.exception('Some error occurred while disabling coupons on Newstore')
        err_msg = str(exc)
        LOGGER.error(f'Error message: {err_msg}')
        return False

def _disable_shopify_coupons(coupon_codes):
    try:
        if not coupon_codes:
            LOGGER.info('No coupons to disable on Shopify')
            return True
        shopify_discount_gql = ShopifyDiscountCodeGQL()
        for coupon in coupon_codes:
            LOGGER.info(f'Disabling coupon: {coupon}')
            shopify_discount_gql.disable_shopify_coupon(coupon)
        return True
    except HTTPError as exc:
        LOGGER.exception('Some error occurred while disabling coupons on Shopify')
        err_msg = str(exc)
        LOGGER.error(f'Error message: {err_msg}')
        return False

def _create_yotpo_order(order_payload):
    LOGGER.info(f'Creating yotpo order: {order_payload}')
    yotpo_handler = YotpoHandler()
    return yotpo_handler.create_order(order_payload)
