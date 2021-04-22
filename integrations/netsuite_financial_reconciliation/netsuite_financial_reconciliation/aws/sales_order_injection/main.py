import asyncio
import logging
import os

from newstore_adapter.connector import NewStoreConnector

from . import params
from . import sales_order
from . import sqs_consumer

NEWSTORE_HANDLER = None

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def handler(event, context):  # pylint: disable=W0613
    global NEWSTORE_HANDLER  # pylint: disable=W0603

    newstore_config = params.get_newstore_config()

    NEWSTORE_HANDLER = NewStoreConnector(
        tenant=os.environ.get('TENANT'),
        context=context,
        host=newstore_config['host'],
        username=newstore_config['username'],
        password=newstore_config['password'],
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

    return sales_order.inject_sales_order(event_payload, order_data)


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
      }
    }
    addresses {
        nodes {
          addressType
          firstName
          lastName
          phone
          salutation
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
              paymentMethod          }
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


def order_data_is_complete(order):
    if not order['id']:
        LOGGER.error(f'Order data does not load. {order}')
        return False
    if not (order['items'] and order['items']['nodes']):
        LOGGER.error(f'Order data does not contain items. {order}')
        return False
    return True
