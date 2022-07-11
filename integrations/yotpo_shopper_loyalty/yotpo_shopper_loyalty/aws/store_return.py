import os
import logging
import json
from lambda_utils.sqs.SqsHandler import SqsHandler
from yotpo_shopper_loyalty.handlers.yotpo_handler import YotpoHandler
from yotpo_shopper_loyalty.handlers.utils import Utils
from newstore_adapter.connector import NewStoreConnector

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

SQS_HANDLER = SqsHandler(os.environ['SQS_YOTPO_ORDER_RETURN_PROCESSED'])

NEWSTORE_HANDLER = None

def handler(event, context):
    LOGGER.info(f'Processing return Event: {event}')
    global NEWSTORE_HANDLER  # pylint: disable=W0603
    utils = Utils.get_instance()
    ns_config = json.loads(utils.get_parameter_store().get_param('newstore'))
    host = ns_config['host']
    username = ns_config['username']
    password = ns_config['password']
    NEWSTORE_HANDLER = NewStoreConnector(
        tenant=os.environ.get('TENANT'),
        context=context,
        raise_errors=True,
        host=host,
        username=username,
        password=password
    )

    for record in event.get('Records', []):
        try:
            response_bool = _process_store_return(record['body'])
            if response_bool:
                LOGGER.info('Event processed, deleting message from queue...')
                SQS_HANDLER.delete_message(record['receiptHandle'])
            else:
                LOGGER.error(f'Failed to process event: {record["body"]}')
        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.exception('Some error occurred while processing the return w.r.t Yotpo')
            err_msg = str(ex)
            LOGGER.error(f'Error message: {err_msg}')
            continue

def _process_store_return(payload_json):
    LOGGER.info(f'Event Payload: {payload_json}')
    # get GQL order from NS
    return_payload = json.loads(payload_json).get('payload', {})
    LOGGER.info('Getting return data from NS...')
    return_data = _get_return_data(return_payload['id'])
    LOGGER.info(f'NS GraphQL Return: {return_data}')
    if not _contains_yotpo_coupons(return_data):
        LOGGER.info('No Yotpo coupons found in return, skipping...')
        return True
    if (return_data.get('order').get('channelType')) == 'store':
        # using order_id as refund_id for Yotpo
        refund_request = _create_yotpo_refund_request(return_data, return_payload['order_id'])
        return _create_yotpo_refund(refund_request)
    return True

def _get_return_data(return_id):
    graphql_query = """
    query Return($id: String!, $tenant: String!) {
        return(id: $id, tenant: $tenant) {
            items {
                nodes {
                    productId
                    quantity
                    refundAmount
                }
            }
            totalRefundAmount
            totalRefundAmountAdjusted
            totalRefundExclTax
            totalRefundTax
            order {
                id
                channelType
                currency
                discounts(first: 100) {
                    nodes {
                        couponCode
                    }
                }
            }
        }
    }

"""
    data = {
        "query": graphql_query,
        "variables": {
            "id": return_id,
            "tenant": os.environ.get('TENANT')
        }
    }

    graphql_response = NEWSTORE_HANDLER.graphql_api_call(data)
    return graphql_response['data']['return']

def _contains_yotpo_coupons(return_data):
    for item in return_data['order']['discounts']['nodes']:
        if item['couponCode'].startswith('FAOC') or item['couponCode'].startswith('FAOU'):
            return True
    return False

def _create_yotpo_refund_request(return_data, refund_id):
    refund_request = {}
    LOGGER.info(f'Creating yotpo refund request')
    refund_request['id'] = refund_id
    refund_request['order_id'] = return_data['order']['id']
    refund_request['total_amount_cents'] = return_data['totalRefundAmount'] * 100
    refund_request['items'] = _get_returned_items(return_data['items']['nodes'])
    refund_request['currency'] = return_data['order']['currency']
    return refund_request

def _get_returned_items(items):
    returned_items = []
    for item in items:
        yotpo_item = {}
        yotpo_item['id'] = item['productId']
        yotpo_item['quantity'] = item['quantity']
        returned_items.append(yotpo_item)
    return returned_items

def _create_yotpo_refund(refund_request):
    LOGGER.info(f'Creating yotpo refund: {refund_request}')
    yotpo_handler = YotpoHandler()
    return yotpo_handler.create_refund(refund_request)
