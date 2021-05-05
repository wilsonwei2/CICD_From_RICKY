import asyncio
import logging
import os
import re
from datetime import timezone, datetime
import pytz

# Runs startup processes (expecting to be 'unused')
import netsuite.netsuite_environment_loader  # pylint: disable=W0611
from netsuite.api.customer import create_customer, lookup_customer_id_by_name_and_email
from netsuite.api.sale import create_cashsale
from netsuite.api.item import get_product_by_name
from netsuite.service import (
    RecordRef,
    CashSaleItem,
    CashSaleItemList, StringCustomFieldRef, CustomFieldList, SelectCustomFieldRef, ListOrRecordRef, Address
)
from newstore_adapter.connector import NewStoreConnector

import json
from . import sqs_consumer
from . import util
from netsuite_financial_reconciliation.helpers.utils import Utils

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

PARAM_STORE = util.get_param_store()

NEWSTORE_HANDLER = None

NETSUITE_CONFIG = util.get_netsuite_config()
NEWSTORE_TO_NETSUITE_LOCATIONS = util.get_newstore_to_netsuite_locations_config()
NEWSTORE_TO_NETSUITE_CHANNEL = util.get_newstore_to_netsuite_channel_config()
NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS = util.get_newstore_to_netsuite_payment_items_config()
NEWSTORE_TO_NETSUITE_PAYMENT_ACCOUNT = util.get_newstore_to_netsuite_payment_account_config()

def handler(event, context):  # pylint: disable=W0613
    global NEWSTORE_HANDLER  # pylint: disable=W0603
    newstore_config = json.loads(PARAM_STORE.get_param('newstore'))
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


def create_cash_sale(order):
    store_id = order['channel']  # when channel_type==store then channel represents the store_id
    subsidiary_id = util.get_subsidiary_id(store_id)

    currency_id = util.get_currency_id(currency_code=order['currency'])

    # Location can be mapped using the channel_id that is the store_id on NewStore
    if store_id in NEWSTORE_TO_NETSUITE_LOCATIONS:
        location_id = NEWSTORE_TO_NETSUITE_LOCATIONS[store_id]['id']
        # selling_location_id = NEWSTORE_TO_NETSUITE_LOCATIONS[store['store_id']]['selling_id']
    else:
        raise Exception('Channel_id %s isn\'t mapped to NetSuite' % store_id)

    custom_fields_list = [
        StringCustomFieldRef(scriptId='custbody_nws_shopifyorderid', value=order['externalId'])
    ]

    placed_at_string = order['placedAt']
    tran_date = datetime.strptime(placed_at_string[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
    tran_date = tran_date.astimezone(pytz.timezone(NETSUITE_CONFIG.get('NETSUITE_DATE_TIMEZONE', 'US/Pacific')))

    cash_sale = {
        'externalId': order['externalId'],  # Order id will be used to lookup order on NetSuite on other newstore events
        'currency': RecordRef(internalId=currency_id),
        'subsidiary': RecordRef(internalId=subsidiary_id),
        'customForm': RecordRef(internalId=int(NETSUITE_CONFIG['cash_sale_custom_form_internal_id'])),
        'location': RecordRef(internalId=location_id),
        'tranDate': tran_date.date(),
        'partner': RecordRef(internalId=int(NETSUITE_CONFIG['newstore_partner_internal_id'])),
        'customFieldList': CustomFieldList(custom_fields_list),
        'department': RecordRef(internalId=1),  # for NewStore originated, and 2 for Shopify originated
    }

    shipping_address = get_order_shipping_address(order)
    if shipping_address:
        # country codes should be fixed using the following codes
        # https://gist.github.com/colinbowern/22027ddfda9ae8461ae2397be7628a11#file-suitetalk-cs-L10451
        address = {
            'country': Utils.get_countries_map().get(shipping_address['country'], '_unitedStates'),
            'state': shipping_address['state'],
            'zip': shipping_address['zipCode'],
            'city': shipping_address['city'],
            'addr1': shipping_address['addressLine1'],
            'addr2': shipping_address['addressLine2'],
        }
        cash_sale['shippingAddress'] = Address(**address)

    return cash_sale


def get_order_shipping_address(order):
    for addr in order['addresses']['nodes']:
        if addr['addressType'] == 'shipping':
            return addr
    return None


def get_customer_info(order):
    store_id = order['channel']  # when channel_type==store then channel represents the store_id
    subsidiary_id = util.get_subsidiary_id(store_id)

    customer_email = order['customerEmail']
    shipping_address = get_order_shipping_address(order)

    customer = None
    if shipping_address and customer_email:
        customer_custom_field_list = [SelectCustomFieldRef(
            scriptId='custentity_nws_profilesource',
            value=ListOrRecordRef(internalId=NEWSTORE_TO_NETSUITE_CHANNEL['store'])
        )]
        if store_id in NEWSTORE_TO_NETSUITE_LOCATIONS:
            store_location_id = NEWSTORE_TO_NETSUITE_LOCATIONS[store_id]['id']
            customer_custom_field_list.append(
                SelectCustomFieldRef(
                    scriptId='custentity_nws_storecreatedby',
                    value=ListOrRecordRef(internalId=store_location_id)
                )
            )
        else:
            LOGGER.warning(f'Store id where the consumer was created {store_id} isn\'t mapped to NetSuite')

        customer = {
            'customForm': RecordRef(internalId=int(NETSUITE_CONFIG['customer_custom_form_internal_id'])),
            'firstName': shipping_address['firstName'].strip()[:32] or '-',
            'lastName': shipping_address['lastName'].strip()[:32] or '-',
            'email': customer_email,
            'phone': shipping_address['phone'],
            'salutation': shipping_address['salutation'],
            'subsidiary': RecordRef(internalId=subsidiary_id),
            'isPerson': True,
            'currencyList': util.get_currency_list(),
        }
        customer['companyName'] = re.sub(' +', ' ', ' '.join(
            (customer['firstName'], customer['lastName'])))
        if customer_custom_field_list:
            customer['customFieldList'] = CustomFieldList(customer_custom_field_list)
    else:
        # If store exists in mapping, default customer for store
        if store_id in NEWSTORE_TO_NETSUITE_LOCATIONS:
            customer = {
                'customForm': RecordRef(internalId=int(NETSUITE_CONFIG['customer_custom_form_internal_id'])),
                'firstName': 'MarineLayer',
                'lastName': NEWSTORE_TO_NETSUITE_LOCATIONS[store_id]['name'],
                'email': NEWSTORE_TO_NETSUITE_LOCATIONS[store_id]['email'],
                'companyName': 'MarineLayer %s' % NEWSTORE_TO_NETSUITE_LOCATIONS[store_id]['name'],
                'subsidiary': RecordRef(internalId=subsidiary_id),
                'currencyList': util.get_currency_list(),
            }

    return customer


def upsert_netsuite_customer(customer):
    netsuite_customer_internal_id = lookup_customer_id_by_name_and_email(customer)
    if netsuite_customer_internal_id:
        return netsuite_customer_internal_id

    LOGGER.info('Create new Customer.')
    return create_customer(customer, return_customer_id=True)


def get_customer_netsuite_internal_id(order):
    customer = get_customer_info(order)
    netsuite_customer_internal_id = upsert_netsuite_customer(customer)
    return RecordRef(internalId=netsuite_customer_internal_id)


def get_capture_transactions(order):  # extracts transactions from order data (GraphQL API response)
    transactions = []
    for transaction in order['paymentAccount']['transactions']['nodes']:
        if transaction['transactionType'] == 'capture':
            transactions.append(transaction)
    return transactions


def create_payment_items(order):
    LOGGER.info("Creating Payment for order")
    LOGGER.info(order)
    payment_items = []
    if order['paymentAccount'] is None:
        return payment_items

    store_id = order['channel']  # when channel_type==store then channel represents the store_id
    subsidiary_id = util.get_subsidiary_id(store_id)
    location_id = NEWSTORE_TO_NETSUITE_LOCATIONS[store_id]['id']

    transactions = get_capture_transactions(order)
    LOGGER.info("Transactions from capture order")
    LOGGER.info(json.dumps(transactions))
    for transaction in transactions:
        payment_method = transaction['instrument']['paymentMethod'].lower()
        if payment_method == 'credit_card':
            provider = transaction['instrument']['paymentProvider'].lower()
            payment_item_id = NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS['credit_card'].get(provider, '')
        elif payment_method == 'gift_card':
            currency = transaction['currency'].lower()
            payment_item_id = NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS.get('gift_card', {}).get(currency, '')
        elif payment_method == 'cash':
            payment_item_id = NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS.get('cash', '')
        else:
            raise ValueError(f'Payment method {payment_method} is not mapped.')

        capture_amount = float(transaction['amount'])
        if capture_amount != 0:
            payment_items.append({
                'item': RecordRef(internalId=payment_item_id),
                'location': RecordRef(internalId=location_id),
                'amount': abs(capture_amount),
                'taxCode': RecordRef(internalId=util.get_not_taxable_id(subsidiary_id=subsidiary_id)) # un -- commented - ML-125
            })
        LOGGER.info("payment item id from paramstore for the transaction ")
        LOGGER.info(payment_item_id)
    return payment_items

# ML-123
def get_payment_method(order):
    transactions = get_capture_transactions(order)
    payment_account_id = None
    ## 1-adyen, cash, giftcard
    ## 2-cash, giftcard, adyen
    ## 4-cash, giftcard, cash
    ## 3-giftcard, giftcard
    """
    in case of split payments, When ‘Adyen’ is involved -  always map to Adyen (internal ID:13)
    Cash & Gift card - map to Cash (internal ID: 1)
    """
    for transaction in transactions:
        payment_method = transaction['instrument']['paymentMethod'].lower()
        if payment_method == 'credit_card':
            provider = transaction['instrument']['paymentProvider'].lower()
            payment_account_id = NEWSTORE_TO_NETSUITE_PAYMENT_ACCOUNT['credit_card'].get(provider, '')
            break
        elif payment_method == 'cash':
            payment_account_id = NEWSTORE_TO_NETSUITE_PAYMENT_ACCOUNT.get('cash', '')
            if len(transactions) > 1:
                continue
            else:
                break
        elif payment_method == 'gift_card':
            currency = transaction['currency'].lower()
            payment_account_id = NEWSTORE_TO_NETSUITE_PAYMENT_ACCOUNT.get('gift_card', {}).get(currency, '')
        else:
            raise ValueError(f'Payment method {payment_method} is not mapped.')
        LOGGER.info("Payment Account id from paramstore for the transaction ")
        LOGGER.info(payment_account_id)

    return payment_account_id


def get_order_items(order):  # extract items from GraphQL API response
    return order['items']['nodes']


def create_cash_sale_items(order):
    cash_sale_items = []

    store_id = order['channel']  # when channel_type==store then channel represents the store_id
    subsidiary_id = util.get_subsidiary_id(store_id)
    location_id = NEWSTORE_TO_NETSUITE_LOCATIONS[store_id]['id']

    items = get_order_items(order)  # extract items from GraphQL API response
    for item in items:
        item_custom_field_list = []

        netsuite_item_id = item['productId']
        if util.is_product_gift_card(netsuite_item_id):
            netsuite_item_id = NETSUITE_CONFIG['netsuite_gift_card_item_id']
        else:
            product = get_product_by_name(netsuite_item_id)
            netsuite_item_id = product['internalId']

        cash_sale_item = {
            'item': RecordRef(internalId=netsuite_item_id),
            'location': RecordRef(internalId=location_id),
            'price': RecordRef(internalId=util.CUSTOM_PRICE),
            'rate': item['pricebookPrice'],
            'taxCode': RecordRef(internalId=util.get_tax_code_id(subsidiary_id=subsidiary_id))
        }

        if float(item['tax']) > 0:
            tax_rate = round(float(item['tax']) * 100 / float(item['pricebookPrice']), 4)
        else:
            tax_rate = 0.0

        item_custom_field_list.append(
            StringCustomFieldRef(
                scriptId='custcol_taxrateoverride',
                value=tax_rate
            )
        )

        if item_custom_field_list:
            cash_sale_item['customFieldList'] = CustomFieldList(item_custom_field_list)

        cash_sale_items.append(cash_sale_item)

        if util.item_has_discount(item):
            cash_sale_items.append(
                {
                    'item': RecordRef(internalId=int(NETSUITE_CONFIG['newstore_discount_item_id'])),
                    'price': RecordRef(internalId=util.CUSTOM_PRICE),
                    'rate': str('-'+str(abs(float(item['itemDiscounts'])+float(item['orderDiscounts'])))),
                    'taxCode': RecordRef(internalId=util.get_not_taxable_id(subsidiary_id=subsidiary_id)),
                    'location': RecordRef(internalId=location_id)
                }
            )

    cash_sale_items += create_payment_items(order)

    return cash_sale_items


def create_cash_sale_item_list(order):
    cash_sale_items_list = []
    cash_sale_items = create_cash_sale_items(order)
    for item in cash_sale_items:
        cash_sale_items_list.append(CashSaleItem(**item))
    return cash_sale_items_list


def get_order_data(order_payload):
    order_id = order_payload["id"]

    graphql_query = """query MyQuery($id: String!, $tenant: String!) {
  order(id: $id, tenant: $tenant) {
    channel
    channelType
    currency
    customerEmail
    customerId
    id
    externalId
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
      transactions {
        nodes {
          amount
          currency
          transactionType
          instrument {
            paymentMethod
            paymentProvider
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


def order_data_is_complete(order):
    if not order['id']:
        LOGGER.error(f'Order data does not load. {order}')
        return False
    if not (order['items'] and order['items']['nodes']):
        LOGGER.error(f'Order data does not contain items. {order}')
        return False
    return True



async def process_events(message):
    order_payload = message.get('payload')

    order = get_order_data(order_payload)  # get order data from GraphQL API

    LOGGER.info('order data in process events')
    LOGGER.info(json.dumps(order))

    if not order_data_is_complete(order):
        raise Exception(f'Error on creating Cash Sale. Required data are not available via GraphQL API. {order}')

    cash_sale = create_cash_sale(order)
    cash_sale['entity'] = get_customer_netsuite_internal_id(order)
    cash_sale['itemList'] = CashSaleItemList(create_cash_sale_item_list(order))
    if order['paymentAccount'] is not None:
        payment_method_id = get_payment_method(order)
        cash_sale['paymentMethod'] = RecordRef(internalId=payment_method_id)

    # LOGGER.info(f'Sending cash sale to NetSuite: {cash_sale}')
    result, _, _ = create_cashsale(cash_sale)

    if not result:
        LOGGER.error(f'Error on creating Cash Sale. Cash Sale not created: {result}')
    else:
        LOGGER.info('Cash Sale created successfully.')
    return result
