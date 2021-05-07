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

# Gets the customer internal id. If the customer is not created yet, a new customer is created
# in Netsuite. Otherwise, it is updated.
def get_customer_internal_id(order_event, order_data):
    store_id = order_data['channel']  # when channel_type==store then channel represents the store_id
    subsidiary_id = get_subsidiary_id(store_id)

    customer_custom_field_list = []

    locations = params.get_newstore_to_netsuite_locations_config()

    email = order_event['customer_email']
    shipping_address = get_order_shipping_address(order_data)

    if shipping_address and email:
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

    else:
        # If store exists in mapping, default customer for store
        if store_id in locations:
            netsuite_customer = {
                'customForm': params.RecordRef(internalId=int(params.get_netsuite_config()['customer_custom_form_internal_id'])),
                'firstName': 'FrankAndOak',
                'lastName': locations[store_id]['name'],
                'email': locations[store_id]['email'],
                'companyName': 'FrankAndOak %s' % locations[store_id]['name'],
                'subsidiary': RecordRef(internalId=subsidiary_id),
                'currencyList': params.get_currency_list()
            }

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

# Creates the Netsuite Sales order out of a Retail Order
def get_sales_order(order_event, order_data):  # pylint: disable=W0613
    service_level = order_event['items'][0].get('shipping_service_level', None)
    logging.info(f'service level is {service_level}')

    if service_level in params.get_newstore_to_netsuite_shipping_methods_config():
        shipping_method_id = params.get_newstore_to_netsuite_shipping_methods_config()[service_level]
    else:
        raise Exception(
            f'Shipping service_level {service_level} is not mapped to NetSuite. Update the mapping to include it.')

    # Map dates and other header fields
    placed_at_string = order_event['placed_at']
    tran_date = datetime.strptime(placed_at_string[:22], '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=timezone.utc)
    tran_date = tran_date.astimezone(pytz.timezone(params.get_netsuite_config().get('NETSUITE_DATE_TIMEZONE', 'US/Eastern')))

    currency_id = params.get_currency_id(currency_code=order_event['currency'])

    # Get Subsidiary id based on the store
    store_id = order_event['channel']
    subsidiary_id = get_subsidiary_id(store_id)

    # Set the channel to the store id using the mapping preference
    if store_id in params.get_newstore_to_netsuite_locations_config():
        locations = params.get_newstore_to_netsuite_locations_config()
        location_id = locations[store_id]['id']
        selling_location_id = locations.get(store_id)['selling_id']
        department_id = params.get_netsuite_config()['store_department_id']
    else:
        raise Exception(f'Location {store_id} cannot be identified.')

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

    # If there is a shipping address, add it to the order
    shipping_address = get_order_shipping_address(order_data)
    if shipping_address:
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

        sales_order['shippingAddress'] = Address(**address)

        LOGGER.info(f'Added Address for retail sales order as -- {address}')

    return sales_order

def get_order_shipping_address(order):
    for addr in order['addresses']['nodes']:
        if addr['addressType'] == 'shipping':
            return addr
    return None


def get_extended_attribute_value(item, name):
    for extended_attribute in item['extended_attributes']:
        if extended_attribute['name'] == name:
            return extended_attribute['value']
    return None


def is_vip_order(order):
    for discount in order['discounts']['nodes']:
        if discount['couponCode'] == 'VIP':
            return True
    return False


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
    store_id = order_event['channel'] # when channel_type==store then channel represents the store_id
    subsidiary_id = get_subsidiary_id(store_id)

    # Get the location for each item from the store id
    if store_id in params.get_newstore_to_netsuite_locations_config():
        locations = params.get_newstore_to_netsuite_locations_config()
        location_id = locations[store_id]['id']

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


def get_subsidiary_id(store_id):
    newstore_to_netsuite_locations = params.get_newstore_to_netsuite_locations_config()
    subsidiary_id = newstore_to_netsuite_locations.get(store_id, {}).get('subsidiary_id')

    if not subsidiary_id:
        raise ValueError(f"Unable to find subsidiary for NewStore location '{store_id}'.")
    return subsidiary_id


def inject_sales_order(order_event, order_data):
    netsuite_sales_order = get_sales_order(order_event, order_data)

    customer_internal_id = get_customer_internal_id(order_event, order_data)
    netsuite_sales_order['entity'] = params.RecordRef(internalId=customer_internal_id)

    netsuite_sales_order_items = []
    sales_order_items = get_sales_order_items(order_event)
    for item in sales_order_items:
        netsuite_sales_order_items.append(SalesOrderItem(**item))
    netsuite_sales_order['itemList'] = SalesOrderItemList(netsuite_sales_order_items)

    result, sale = create_salesorder(netsuite_sales_order)
    if not result:
        raise Exception(f'Error on creating SalesOrder. SalesOrder not created. {result}')

    LOGGER.info('SalesOrder created successfully.')
    return result, sale, sales_order_items
