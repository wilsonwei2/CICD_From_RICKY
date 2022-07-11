import os
import logging
import json
from lambda_utils.sqs.SqsHandler import SqsHandler
from yotpo_shopper_loyalty.handlers.yotpo_handler import YotpoHandler
from newstore_adapter.connector import NewStoreConnector

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

SQS_HANDLER = SqsHandler(os.environ['SQS_YOTPO_ORDER_CANCELLED'])

NEWSTORE_HANDLER = None

def handler(event, context):
    LOGGER.info(f'Processing cancellation Event: {event}')
    global NEWSTORE_HANDLER  # pylint: disable=W0603
    NEWSTORE_HANDLER = NewStoreConnector(
        tenant=os.environ.get('TENANT'),
        context=context,
        raise_errors=True
    )

    for record in event.get('Records', []):
        try:
            response_bool = _process_cancellation(record['body'])
            if response_bool:
                LOGGER.info('Event processed, deleting message from queue...')
                SQS_HANDLER.delete_message(record['receiptHandle'])
            else:
                LOGGER.error(f'Failed to process event: {record["body"]}')
        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.exception('Some error occurred while processing the cancellation w.r.t Yotpo')
            err_msg = str(ex)
            LOGGER.error(f'Error message: {err_msg}')
            continue

def _process_cancellation(payload_json):
    LOGGER.info(f'Event Payload: {payload_json}')
    # get GQL order from NS
    order_payload = json.loads(payload_json).get('payload', {})
    LOGGER.info('Getting order data from NS...')
    order = _get_order_data(order_payload['id'])
    LOGGER.info(f'NS GraphQL Order: {order}')
    # using order uuid as refund id for Yotpo
    refund_request = _create_yotpo_refund_request(order, order_payload['id'])
    if (order_payload.get('channel_type')) == 'store':
        return _create_yotpo_refund(refund_request)
    return True

def _get_order_data(order_id):
    graphql_query = """
    query Order($id: String!, $tenant: String!) {
        order(id: $id, tenant: $tenant) {
            channel
            channelType
            currency
            customerEmail
            customerId
            id
            externalId
            demandLocationId
            placedAt
            tenant
            items {
                nodes {
                    id
                    pricebookPrice
                    productId
                    tax
                    itemDiscounts
                    orderDiscounts
                    status
                    listPrice
                    quantity
                }
            }
         }
    }
"""
    data = {
        "query": graphql_query,
        "variables": {
            "id": order_id,
            "tenant": os.environ.get('TENANT')
        }
    }

    graphql_response = NEWSTORE_HANDLER.graphql_api_call(data)
    return graphql_response['data']['order']

def _create_yotpo_refund_request(order, refund_id):
    refund_request = {}
    LOGGER.info(f'Creating yotpo refund request')
    refund_request['id'] = refund_id
    refund_request['order_id'] = order['id']
    refund_request['total_amount_cents'] = _calculate_total_cancel_amount(order['items']['nodes'])
    refund_request['items'] = _get_cancelled_items(order['items']['nodes'])
    refund_request['currency'] = order['currency']
    return refund_request

def _calculate_total_cancel_amount(items):
    total_amount_cents = 0
    for item in items:
        total_amount_cents += (item['listPrice'] + item['tax']) * 100
    return total_amount_cents

def _get_cancelled_items(items):
    cancelled_items = []
    for item in items:
        if item['status'] == 'cancelled':
            yotpo_item = {}
            yotpo_item['id'] = item['productId']
            yotpo_item['quantity'] = item['quantity']
            cancelled_items.append(yotpo_item)
    return cancelled_items

def _create_yotpo_refund(refund_request):
    LOGGER.info(f'Creating yotpo refund: {refund_request}')
    yotpo_handler = YotpoHandler()
    return yotpo_handler.create_refund(refund_request)
