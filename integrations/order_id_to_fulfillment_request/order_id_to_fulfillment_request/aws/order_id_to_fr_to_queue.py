import json
import logging
import os

from lambda_utils.sqs.SqsHandler import SqsHandler
from order_id_to_fulfillment_request.handlers.utils import Utils

LOGGER = logging.getLogger(__name__)
LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER.setLevel(LOG_LEVEL)
QUEUE_NAME = os.environ.get('SQS_NAME')

def handler(event, context): # pylint: disable=W0613
    """
    This is the webhook that is triggered by Yotpo.
    """
    LOGGER.info(f"Event: {event}")
    ids = json.dumps(event)
    ids_list = json.loads(ids)
    LOGGER.info(f"order_ids: {ids_list['order_ids']}")
    for order_id in ids_list['order_ids']:
        _get_fulfillment_requests(order_id)
    return {
        'statusCode': 200
    }


def _get_fulfillment_requests(order_id):
    """
    This function gets a list of fulfillment requests for an order.
    To summarize, this function does the following:
        1. get list of external order ids - i can help you with the serverless code for this
        2. for each order id call the NewStore API get order (https://{{tenant_name}}.{{api_env}}.newstore.net/v0/d/external_orders/UATCA00006789)
        3. get the uuid from the get order response
        4. use a graphql call to get the fulfillment data for each fulfillment in the order
        5. format the response from graphql to match the fulfillment event that is normally received by the integration
        6. send the formatted data to the sqs
    """
    utils_obj = Utils.get_instance()
    ns_handler = utils_obj.get_ns_handler()
    order_details = ns_handler.get_order_by_external_id(order_id)
    LOGGER.info(f"order_id: {order_id} and order_uuid: {order_details['order_uuid']}")

    fulfillment_requests = ns_handler.get_fulfillment_requests(order_details['order_uuid'])
    LOGGER.info(f"fulfillment requests for order: {order_id} \n {fulfillment_requests}")

    for fulfillment_request in fulfillment_requests['fulfillment_requests']:
        graphql_fulfillment_request = get_fulfillment_request(fulfillment_request)
        payload = {"payload": graphql_fulfillment_request}
        LOGGER.info(f"Message: {payload}")
        _push_to_queue(payload)
    LOGGER.info(f"processed order: {order_id}")


def get_fulfillment_request(fulfillment_payload):
    fulfillment_id = fulfillment_payload["id"]

    graphql_query = """query MyQuery($id: String!, $tenant: String!) {
        fulfillmentRequest(id: $id, tenant: $tenant) {
            fulfillmentLocationId       
            id          
            items(filter: {trackingCode: {isNull: false}}) { 
                edges {
                    node {
                            id        
                            carrier        
                            productId        
                            trackingCode        
                            shippedAt 
                        }
                    }
                }           
            associateId              
            serviceLevel              
            orderId              
            logicalTimestamp 
        }
    }"""
    data = {
        "query": graphql_query,
        "variables": {
            "id": fulfillment_id,
            "tenant": os.environ.get('TENANT_TEMP')
        }
    }
    utils_obj = Utils.get_instance()
    ns_handler = utils_obj.get_ns_handler()
    graphql_response = ns_handler.graphql_api_call(data) # pylint: disable=E1101
    return graphql_response['data']['fulfillmentRequest']


def _push_to_queue(message):
    """
    This function pushes the fulfillment request to queue
    """
    sqs_handler = SqsHandler(queue_name=QUEUE_NAME)
    sqs_handler.push_message(message_group_id=message['payload']['id'], message=json.dumps(message))
    LOGGER.info(f'Message pushed to SQS: {sqs_handler.queue_name}')
