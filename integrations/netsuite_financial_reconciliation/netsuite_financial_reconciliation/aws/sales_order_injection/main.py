import asyncio
import logging
import os

from newstore_adapter.connector import NewStoreConnector

from . import params  # pylint: disable=unused-import
from . import sales_order
from . import sqs_consumer

NEWSTORE_HANDLER = None

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def handler(event, context):  # pylint: disable=W0613
    global NEWSTORE_HANDLER  # pylint: disable=W0603

    NEWSTORE_HANDLER = NewStoreConnector(
        tenant=os.environ.get('TENANT'),
        context=context,
        raise_errors=True
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = sqs_consumer.consume(process_events, os.environ['SQS_QUEUE'])
    loop.run_until_complete(task)
    loop.stop()
    loop.close()


async def process_events(message):
    LOGGER.info('Message from Handler')

    LOGGER.info(message)

    event_payload = message.get('payload')

    order_data = get_order_data(event_payload['id'])  # get order data from GraphQL API

    if not order_data_is_complete(order_data):
        raise Exception(f'Error on creating SalesOrder. Required data are not available via GraphQL API. {order_data}')

    consumer = await get_consumer(order_data)

    return sales_order.inject_sales_order(event_payload, order_data, consumer)


def get_order_data(order_id):
    graphql_query = """query MyQuery($id: String!, $tenant: String!) {
  order(id: $id, tenant: $tenant) {
    channel
    channelType
    currency
    customerEmail
    customerId
    id
    externalId
    demandLocationId
    isExchange
    isHistorical
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
        extendedAttributes(first: 20) {
          nodes {
            name
            value
          }
        }
      }
    }
    addresses {
        nodes {
            addressType
            firstName
            lastName
            phone
            salutation
            country
            city
            addressLine1
            addressLine2
            state
            zipCode
        }
    }
    paymentAccount {
      transactions(filter: {transactionType: {equalTo: "authorize"}}) {
        nodes {
          amount
          currency
          transactionType
          instrument {
            paymentWallet
            paymentProvider
            paymentOrigin
            paymentMethod
          }
        }
      }
    }
    fulfillmentRequests(first: 50) {
      nodes {
        id
        items(first: 50) {
          nodes {
            id
            productId
          }
        }
      }
    }
  }
}"""
    data = {
        "query": graphql_query,
        "variables": {
            "id": order_id,
            "tenant": os.environ.get('TENANT')
        }
    }

    graphql_response = NEWSTORE_HANDLER.graphql_api_call(data)
    return graphql_response['data']['order']


async def get_consumer(order):
    if order is not None:
        email = order.get('customerEmail')
    return NEWSTORE_HANDLER.get_consumer(email) if email else None


def order_data_is_complete(order):
    if order is not None:
        if not order['id']:
            LOGGER.error(f'Order data does not load. {order}')
            return False
        if not (order['items'] and order['items']['nodes']):
            LOGGER.error(f'Order data does not contain items. {order}')
            return False
    return True
