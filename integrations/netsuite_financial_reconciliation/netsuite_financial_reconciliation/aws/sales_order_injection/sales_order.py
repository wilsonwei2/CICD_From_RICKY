from datetime import datetime, timezone
import logging
import re
import pytz

from netsuite.api.customer import lookup_customer_id_by_name_and_email, update_customer, create_customer
from netsuite.api.sale import create_salesorder, initialize_record, upsert_list
from netsuite.service import (
    SalesOrderItem,
    SalesOrderItemList,
    SelectCustomFieldRef,
    ListOrRecordRef,
    CustomFieldList,
    StringCustomFieldRef,
    RecordRef,
    ItemSearchBasic,
    SearchStringField,
    SearchBooleanField,
    Address
)
from netsuite.utils import search_records_using

from . import params
from .util import get_formatted_phone
from netsuite_financial_reconciliation.helpers.utils import Utils

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


def get_customer_internal_id(order_event, order_data):
    store_id = order_data['demandLocationId']
    subsidiary_id = 1

    customer_custom_field_list = []
    if order_event['channel_type'] == 'web':
        customer_custom_field_list += [
            SelectCustomFieldRef(
                scriptId='custentity_nws_profilesource',
                value=ListOrRecordRef(internalId=str(params.get_newstore_to_netsuite_channel_config()['web']))
            ),
            SelectCustomFieldRef(
                scriptId='custentity_nws_storecreatedby',
                value=ListOrRecordRef(internalId=params.get_netsuite_config()['shopify_location_id'])
            )
        ]
    else:
        locations = params.get_newstore_to_netsuite_locations_config()
        store_id = order_event['channel']
        if store_id in locations:
            customer_custom_field_list.append(
                SelectCustomFieldRef(
                    scriptId='custentity_nws_profilesource',
                    value=ListOrRecordRef(internalId=params.get_newstore_to_netsuite_channel_config()['store'])
                )
            )
            store_location_id = locations[store_id]['id']
            customer_custom_field_list.append(
                SelectCustomFieldRef(
                    scriptId='custentity_nws_storecreatedby',
                    value=ListOrRecordRef(internalId=store_location_id)
                )
            )
        else:
            LOGGER.error(f'Store id where the consumer was created {store_id} isn\'t mapped to NetSuite')

    first_name = order_event['shipping_address']['first_name']
    last_name = order_event['shipping_address']['last_name']
    email = order_event['customer_email']
    phone_number = order_event['shipping_address']['phone']

    netsuite_customer = {
        'customForm': params.RecordRef(internalId=int(params.get_netsuite_config()['customer_custom_form_internal_id'])),
        'firstName': first_name[:32] if first_name.strip() else '-',
        'lastName': last_name[:32] if last_name.strip() else '-',
        'email': email,
        'phone': get_formatted_phone(phone_number),
        'subsidiary': params.RecordRef(internalId=subsidiary_id),
        'isPerson': True,
        'currencyList': params.get_currency_list(),
        'customFieldList': customer_custom_field_list
    }

    netsuite_customer['companyName'] = re.sub(' +', ' ', ' '.join((netsuite_customer['firstName'],
                                                                   netsuite_customer['lastName'])))

    # If customer is found we update it, but only if it is the same subsidiary
    netsuite_customer_internal_id = lookup_customer_id_by_name_and_email(netsuite_customer)
    if netsuite_customer_internal_id:
        LOGGER.info('Customer exists, updating the customer.')
        netsuite_customer['internalId'] = netsuite_customer_internal_id
        update_customer(netsuite_customer)
        return netsuite_customer_internal_id

    LOGGER.info('Creating new Customer.')
    # This returns the Customer or None if there is any error
    result = create_customer(netsuite_customer)
    if not result:
        raise Exception(f'Error on creating Customer. Customer not created. {result}')

    return result['internalId']


def get_payment_transactions(order_data):
    return order_data['paymentAccount']['transactions']['nodes']


def get_payment_items(order_event, order_data, location):
    LOGGER.info('Mapping payment items')
    subsidiary_id = 1
    payment_items = []
    if order_data['paymentAccount'] is None:
        return payment_items

    is_exchange_order = order_data['isExchange']
    transactions = get_payment_transactions(order_data)

    for transaction in transactions:
        method = transaction['instrument']['paymentMethod'].lower()
        provider = transaction['instrument']['paymentProvider'].lower()

        # When exchange, use Exchange credit as payment
        if is_exchange_order:
            payment_item_id = params.get_newstore_to_netsuite_payment_items_config().get('store_credit')
        elif method == 'credit_card':
            payment_item_id = params.get_newstore_to_netsuite_payment_items_config()[method].get(provider, '')
        elif method == 'gift_card':
            currency = transaction['currency'].lower()
            payment_item_id = params.get_newstore_to_netsuite_payment_items_config().get(method, {}).get(currency, '')
        else:
            payment_item_id = params.get_newstore_to_netsuite_payment_items_config().get(method, '')

        # In case the payment item isn't mapped and the order is WEB utilize Shopify payment item as default
        if not payment_item_id and order_event['channel_type'] == 'web':
            payment_item_id = params.get_newstore_to_netsuite_payment_items_config().get('shopify', '')

        if not payment_item_id:
            if method == 'credit_card':
                msg = f'Payment Item for payment method {method} and provider {provider} not mapped.'
            else:
                msg = f'Payment Item for payment method {method} not mapped.'
            raise ValueError(msg)

        capture_amount = float(transaction['amount'])
        if capture_amount != 0:
            payment_item = {
                'item': params.RecordRef(internalId=payment_item_id),
                'amount': abs(capture_amount),
                'taxCode': params.RecordRef(internalId=params.get_not_taxable_id(subsidiary_id=subsidiary_id)),
                'location': location
            }

            payment_items.append(payment_item)
            LOGGER.info(f'Payment Item for payment method {method} added to items.')

    return payment_items


def get_sales_order(order_event, order_data):  # pylint: disable=W0613
    service_level = order_event['items'][0].get('shipping_service_level', None)
    logging.info(f'service level is {service_level}')

    if service_level in params.get_newstore_to_netsuite_shipping_methods_config():
        shipping_method_id = params.get_newstore_to_netsuite_shipping_methods_config()[service_level]
    else:
        raise Exception(
            f'Shipping service_level {service_level} is not mapped to NetSuite. Update the mapping to include it.')

    placed_at_string = order_event['placed_at']
    tran_date = datetime.strptime(placed_at_string[:22], '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=timezone.utc)
    tran_date = tran_date.astimezone(pytz.timezone(params.get_netsuite_config().get('NETSUITE_DATE_TIMEZONE', 'US/Eastern')))

    subsidiary_id = 1

    currency_id = params.get_currency_id(currency_code=order_event['currency'])

    if order_event['channel_type'] == 'web':
        location_id = params.get_netsuite_config()['shopify_location_id']
        selling_location_id = params.get_netsuite_config()['shopify_selling_location_id']
        department_id = params.get_netsuite_config()['web_department_id']
    elif order_event['channel'] in params.get_newstore_to_netsuite_locations_config():
        locations = params.get_newstore_to_netsuite_locations_config()
        location_id = locations.get(order_event['channel'])['id']
        selling_location_id = locations.get(order_event['channel'])['selling_id']
        department_id = params.get_netsuite_config()['store_department_id']
    else:
        raise Exception(f'Location {order_event["channel"]} cannot be identified.')

    customer_name = ' '.join(filter(None, [order_event['shipping_address']['first_name'],
                                           order_event['shipping_address']['last_name']])) or '-'

    address = {
        'country': Utils.get_countries_map().get(order_event['shipping_address']['country'], '_unitedStates'),
        'state': order_event['shipping_address']['state'],
        'zip': order_event['shipping_address']['zip_code'],
        'city': order_event['shipping_address']['city'],
        'addr1': order_event['shipping_address']['address_line_1'],
        'addr2': order_event['shipping_address']['address_line_2'],
        'addressee': customer_name
    }
    LOGGER.info(f"Added Address for sales order as -- {address}")

    sales_order = {
        'externalId': order_event['external_id'],
        'tranDate': tran_date.date(),
        'currency': params.RecordRef(internalId=currency_id),
        'subsidiary': params.RecordRef(internalId=subsidiary_id),
        'customForm': params.RecordRef(internalId=int(params.get_netsuite_config()['sales_order_custom_form_internal_id'])),
        'location': params.RecordRef(internalId=location_id),
        # 'partner': params.RecordRef(internalId=int(params.get_netsuite_config()['newstore_partner_internal_id'])),
        'shipMethod': params.RecordRef(internalId=shipping_method_id),
        'shippingCost': order_event['shipping_total'],
        'class': params.RecordRef(internalId=selling_location_id),
        'department': params.RecordRef(internalId=department_id),
        'customFieldList': CustomFieldList([
            StringCustomFieldRef(
                scriptId='custbodyaccumula_ecomid',
                value=order_event['external_id']
            )
        ])
    }

    if not order_event['shipping_tax'] > 0:
        sales_order['customFieldList']['customField'].append(
            StringCustomFieldRef(
                scriptId='custbody_afaps_ship_taxrate_override',
                value=0.0
            )
        )

    sales_order['shippingAddress'] = Address(**address)

    return sales_order


def get_extended_attribute_value(item, name):
    for extended_attribute in item['extended_attributes']:
        if extended_attribute['name'] == name:
            return extended_attribute['value']
    return None


def get_product_by_external_id(name):
    item_search = ItemSearchBasic(
        externalIdString=SearchStringField(
            searchValue=name,
            operator='is'
        ))
    result = search_records_using(item_search)
    search_result = result.body.searchResult
    if search_result.status.isSuccess:
        # The search can return nothing, meaning the product doesn't exist
        if search_result.recordList:
            return search_result.recordList.record[0]
    return None


def get_product_by_name(name):
    item_search = ItemSearchBasic(
        itemId=SearchStringField(
            searchValue=name,
            operator='is'
        ),
        isInactive=SearchBooleanField(
            searchValue=False
        )
    )
    result = search_records_using(item_search)
    search_result = result.body.searchResult
    if search_result.status.isSuccess:
        # The search can return nothing, meaning the product doesn't exist
        if search_result.recordList:
            return search_result.recordList.record[0]
        # If the name isn't in itemId then look at external id
        return get_product_by_external_id(name)
    return None


def get_sales_order_items(order_event):
    subsidiary_id = 1
    if order_event['channel_type'] == 'web':
        location_id = params.get_netsuite_config()['shopify_location_id']
    elif order_event['channel'] in params.get_newstore_to_netsuite_locations_config():
        locations = params.get_newstore_to_netsuite_locations_config()
        location_id = locations.get(order_event['channel'])['id']

    sales_order_items = []

    order_items = order_event['items']

    for item in order_items:
        item_custom_field_list = []

        netsuite_item_id = item['product_id']
        if netsuite_item_id in params.get_giftcard_product_ids_config():
            netsuite_item_id = params.get_netsuite_config()['netsuite_gift_card_item_id']
        else:
            product = get_product_by_name(netsuite_item_id)
            netsuite_item_id = product['internalId']

        sales_order_item = {
            'item': RecordRef(internalId=netsuite_item_id),
            'price': params.RecordRef(internalId=params.CUSTOM_PRICE),
            'rate': str(item['pricebook_price']),
            'location': params.RecordRef(internalId=location_id),
            'taxCode': params.RecordRef(internalId=params.get_tax_code_id(subsidiary_id=subsidiary_id)),
            'quantity': 1
        }

        if item['status'] == 'canceled':
            item_custom_field_list.append(
                StringCustomFieldRef(
                    scriptId='custcol_nws_fulfillrejected',
                    value='T'
                )
            )

        if item['tax'] > 0:
            tax = float(item['tax'])
            duties = get_extended_attribute_value(item, 'duty')
            if duties:
                tax = tax - float(duties)
                item_duty_charge = {
                    'item': params.RecordRef(internalId=int(params.get_netsuite_config()['international_duty_id'])),
                    'price': params.RecordRef(internalId=params.CUSTOM_PRICE),
                    'rate': duties,
                    'taxCode': params.RecordRef(internalId=params.get_not_taxable_id(subsidiary_id=subsidiary_id))
                }
                sales_order_items.append(item_duty_charge)

            price = float(item['pricebook_price'])
            tax_rate = round(tax * 100 / price, 4)
        else:
            tax_rate = 0.0

        item_custom_field_list.append(
            StringCustomFieldRef(
                scriptId='custcol_taxrateoverride',
                value=tax_rate
            )
        )

        if item_custom_field_list:
            sales_order_item['customFieldList'] = CustomFieldList(item_custom_field_list)

        sales_order_items.append(sales_order_item)

        has_discount = float(item['item_discounts']) > 0 or float(item['order_discounts']) > 0
        if has_discount:
            sales_order_items.append(
                {
                    'item': RecordRef(internalId=int(params.get_netsuite_config()['newstore_discount_item_id'])),
                    'price': params.RecordRef(internalId=params.CUSTOM_PRICE),
                    'rate': str('-'+str(abs(float(item['item_discounts'])+float(item['order_discounts'])))),
                    'taxCode': params.RecordRef(internalId=params.get_not_taxable_id(subsidiary_id=subsidiary_id)),
                    'location': RecordRef(internalId=location_id)
                }
            )
    return sales_order_items



def inject_invoice(sale, external_id):
    #invoice_items_list = []
    #for item in sales_order_items:
    #    invoice_items_list.append(InvoiceItem(**item))
    sale_internal_id = sale if isinstance(sale, int) else sale.internalId

    invoice = initialize_record('invoice', 'salesOrder', sale_internal_id)
    LOGGER.info(f'Invoice initialized: {invoice}')
    # invoice['externalId'] = str(external_id)
    #invoice['itemList'] = InvoiceItemList(invoice_items_list)
    invoice['externalId'] = f'{external_id}-invoice'
    del invoice['itemList']
    #subsidiary_id = 1 ## ML-106
    # invoice['subsidiary'] = params.RecordRef(internalId=subsidiary_id)
    #del invoice["totalCostEstimate"]
    #del invoice["estGrossProfitPercent"]
    #del invoice["customFieldList"]
    #del invoice["discountTotal"]
    #del invoice["giftCertApplied"]

    return upsert_list([invoice])


def inject_sales_order(order_event, order_data):
    sales_order = get_sales_order(order_event, order_data)
    netsuite_sales_order = sales_order

    customer_internal_id = get_customer_internal_id(order_event, order_data)
    netsuite_sales_order['entity'] = params.RecordRef(internalId=customer_internal_id)

    netsuite_sales_order_items = []
    sales_order_items = get_sales_order_items(order_event)
    # TODO Payment Items are not setup in Netsuite - so uncomment for now pylint: disable=fixme
    # sales_order_items += get_payment_items(order_event, order_data, sales_order['location'])
    for item in sales_order_items:
        netsuite_sales_order_items.append(SalesOrderItem(**item))
    netsuite_sales_order['itemList'] = SalesOrderItemList(netsuite_sales_order_items)

    result, sale, flag_dup = create_salesorder(netsuite_sales_order)
    if not result:
        raise Exception(f'Error on creating SalesOrder. SalesOrder not created. {result}')

    # TODO Invoices are created automatically from a Customer Deposit for F&O - don't inject pylint: disable=fixme
    # the invoice
    # Only attempt to create invoice if record is not duplicated
    # if not flag_dup:
    #    if not inject_invoice(sale, netsuite_sales_order['externalId']):
    #        raise Exception(f'Error on creating Invoice.')

    LOGGER.info('SalesOrder created successfully.')
    return result, sale, sales_order_items
