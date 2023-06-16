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

    mapped_coupon_result = perform_data_mapping(order_payload)
    LOGGER.info(f'mapped_coupon_result: {mapped_coupon_result}')

    coupon_codes = list([discount.get('coupon_code') for discount in discounts
                         if (discount.get('coupon_code').startswith("FAOU")
                             or discount.get('coupon_code').startswith("FAOC"))])
    if (order_payload.get('channel_type')) == 'web':
        return _disable_ns_coupons(coupon_codes, mapped_coupon_result)
    if (order_payload.get('channel_type')) == 'store':
        if _disable_shopify_coupons(coupon_codes) and _create_yotpo_order(order_payload) and _disable_ns_coupons(coupon_codes, mapped_coupon_result):
            return True
    return False


def _disable_ns_coupons(coupon_codes, mapped_coupon_result):
    if not coupon_codes:
        LOGGER.info('No coupons to disable on Newstore')
        return True
    try:
        LOGGER.info(f'Disabling coupons: {coupon_codes}')

        coupon_name_prefix = 'YOTPO_AWS_'

        # Iterate over the array
        for mapped_coupon in mapped_coupon_result:
            # Iterate over the desired coupon code
            for coupon_code in coupon_codes:
                # Check if the coupon_code exists in the dictionary
                if coupon_code in mapped_coupon:
                    LOGGER.info(f'Disabling coupon: {coupon_code}')
                    # Retrieve the value using the coupon_code
                    value = mapped_coupon[coupon_code]
                    target_coupon_name = ''
                    if value["type"] == 'CartLevelFixed':
                        target_coupon_name = coupon_name_prefix + '$'
                    else:
                        target_coupon_name = coupon_name_prefix + '%'
                    target_coupon_name = target_coupon_name + str(int(value["amount"])) + '_Off'

                    target_coupon_info = NEWSTORE_HANDLER.get_coupons(target_coupon_name)

                    NEWSTORE_HANDLER.disable_coupon(coupon_code, target_coupon_info)
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


def perform_data_mapping(payload):
    coupon_mapping = {}

    for item in payload['items']:
        for discount in item['discounts']:
            coupon_code = discount['coupon_code']
            value = discount['price_adjustment']
            action = discount['action']
            level = discount['level']

            if coupon_code not in coupon_mapping:
                coupon_mapping[coupon_code] = {
                    'type': '',
                    'amount': 0
                }

            coupon_mapping[coupon_code]['amount'] += value

            if action == 'fixed' and level == 'order':
                coupon_mapping[coupon_code]['type'] = 'CartLevelFixed'

    output = []
    for coupon_code, coupon_data in coupon_mapping.items():
        output.append({coupon_code: coupon_data})

    return output
