import json
import logging
import os

from yotpo_shopper_loyalty.handlers.utils import Utils

LOGGER = logging.getLogger(__name__)
LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER.setLevel(LOG_LEVEL)

def handler(event, context): # pylint: disable=W0613
    """
    This is the webhook that is triggered by Yotpo.
    """
    LOGGER.info(f"Event: {event}")

    event_body = json.loads(event['body'])
    # log the event body

    if event_body.get('topic') == 'swell/redemption/created':
        # read event body and create coupons in NewStore accordingly
        _create_ns_coupons(event_body)
    return {
        'statusCode': 200
    }


def _create_ns_coupons(event_body):
    """
    This function creates a coupon definition and subsequently
    a coupon in NewStore. To summarize, this function does the following:
        1. Retrieves the corresponding discount rule id in NewStore from the param store
        2. Creates a coupon definition in NewStore
        3. Creates a coupon in NewStore
    """
    utils_obj = Utils.get_instance()
    ns_handler = utils_obj.get_ns_handler()
    coupon_code = event_body.get('redemption').get('reward_text')
    redemption_option_id = event_body.get('redemption_option').get('id')
    redemption_option_name = event_body.get('redemption_option').get('name')
    ns_discount_rule_id = _get_ns_discount_rule_id(utils_obj, redemption_option_id)
    coupon_definition_label = f"{coupon_code}_{redemption_option_id}"
    LOGGER.info(f"ns_discount_rule_id: {ns_discount_rule_id}")
    coupon_definition_response = ns_handler.create_coupon_definition(
        coupon_code,
        coupon_definition_label,
        ns_discount_rule_id
    )
    LOGGER.info(f"coupon_definition_response: {coupon_definition_response}")
    create_coupon_response = ns_handler.create_coupon(coupon_definition_label, redemption_option_name)
    LOGGER.info(f"create_coupon_response: {create_coupon_response}")



def _get_ns_discount_rule_id(utils_obj, redempttion_option_id):
    """
    This function returns the discount rule id in NewStore.
    """
    ns_discount_rules = json.loads(
        utils_obj.
        get_parameter_store().
        get_param('yotpo_ns_discount_rules_mapping')
    )
    LOGGER.info(f"redempttion_option_id: {redempttion_option_id}")
    LOGGER.info(f"fetched ns_discount_rules from param store: {ns_discount_rules}")
    return ns_discount_rules.get(str(redempttion_option_id))
