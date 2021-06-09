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

    consumer = await get_consumer(order_data)

    # Process virtual/electronic gift cards if needed
    await ship_virtual_gift_cards(order_data)

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
    email = order.get('customerEmail')
    return NEWSTORE_HANDLER.get_consumer(email) if email else None


def order_data_is_complete(order):
    if not order['id']:
        LOGGER.error(f'Order data does not load. {order}')
        return False
    if not (order['items'] and order['items']['nodes']):
        LOGGER.error(f'Order data does not contain items. {order}')
        return False
    return True

#
# Virtual or Electronic Gift Cards need to be set to shipped and paid immediately. This function
# checks if there are gift cards in the order, and generates a shipment if so.
#
async def ship_virtual_gift_cards(customer_order):
    items_to_ship = []
    for line_item in customer_order['items']['nodes']:
        if is_virtual_gift_card(line_item) and line_item['status'] != 'canceled' and line_item['status'] != 'completed':
            LOGGER.info(f'Item {line_item} is a virtual gift card.')
            items_to_ship.append(line_item)
    if not items_to_ship:
        return items_to_ship

    shipment_json = {
        'line_items': [
            {
                'product_ids': [item['productId'] for item in items_to_ship],
                'shipment': {
                    'tracking_code': 'N/A',
                    'carrier': 'N/A'
                }
            }
        ]
    }

    fulfillment_id = get_egc_fulfillment_id(customer_order, items_to_ship[0])

    if not NEWSTORE_HANDLER.send_shipment(fulfillment_id, shipment_json):
        raise Exception('Fulfillment request was not informed of shipping for virtual gift cards.')
    LOGGER.info('Fulfillment request informed of shipping for virtual gift cards.')
    return items_to_ship


#
# Gets the first found fulfillment request id with an EGC. There
# should be only one fulfillment request with EGCs, so no further check is done.
#
def get_egc_fulfillment_id(customer_order, line_item):
    fulfillment_id = None
    if customer_order['fulfillmentRequests']['nodes']:
        for ffr in customer_order['fulfillmentRequests']['nodes']:
            for item in ffr['items']['nodes']:
                if item['productId'] == line_item['productId']:
                    fulfillment_id = ffr['id']
                    break

    LOGGER.info(f'fulfillment_id for virtual gift cards is {fulfillment_id}')

    return fulfillment_id

#
# Checks if the given line item is a virtual/electronic gift card. A GraphQL payload is required.
#
def is_virtual_gift_card(line_item):
    is_gc = get_extended_attribute(line_item['extendedAttributes']['nodes'], 'is_gift_card')
    requires_shipping = get_extended_attribute(line_item['extendedAttributes']['nodes'], 'requires_shipping')
    return is_gc == 'True' and requires_shipping == 'False'


def get_extended_attribute(extended_attributes, key):
    if extended_attributes:
        for attr in extended_attributes:
            if attr['name'] == key:
                return attr['value']
    return ''
