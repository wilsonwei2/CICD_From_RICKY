from datetime import datetime, timezone
import logging
import numbers
import re
import pytz

from netsuite.api.customer import lookup_customer_id_by_email, update_customer, create_customer
from netsuite.api.sale import create_salesorder
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
from pom_common.netsuite import TaxManager

from . import params
from .util import get_formatted_phone, require_shipping
from netsuite_financial_reconciliation.helpers.utils import Utils

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

CITY_SUBSTRING_LIMIT = 49


# Removes any incompatible chars from a string - mainly used to filter values
# entered by customers in the webshop.
def remove_incompatible_chars(string):
    return remove_emojis(''.join(c for c in string if valid_xml_char_ordinal(c)))


def valid_xml_char_ordinal(c):
    codepoint = ord(c)
    return (
        0x20 <= codepoint <= 0xD7FF or
        codepoint in (0x9, 0xA, 0xD) or
        0xE000 <= codepoint <= 0xFFFD or
        0x10000 <= codepoint <= 0x10FFFF
        )


def remove_emojis(string):
    pattern = re.compile("["
                           u"\U0001F600-\U0001F64F"  # emoticons
                           u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                           u"\U0001F680-\U0001F6FF"  # transport & map symbols
                           u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                           u"\U00002500-\U00002BEF"  # chinese char
                           u"\U00002702-\U000027B0"
                           u"\U00002702-\U000027B0"
                           u"\U000024C2-\U0001F251"
                           u"\U0001f926-\U0001f937"
                           u"\U00010000-\U0010ffff"
                           u"\u2640-\u2642"
                           u"\u2600-\u2B55"
                           u"\u200d"
                           u"\u23cf"
                           u"\u23e9"
                           u"\u231a"
                           u"\ufe0f"  # dingbats
                           u"\u3030"
                           "]+", flags=re.UNICODE)
    return pattern.sub(r'', string)

# Gets the customer internal id. If the customer is not created yet, a new customer is created
# in Netsuite. Otherwise, it is updated.
def get_customer_internal_id(order_event, order_data, consumer):  # pylint: disable=too-many-statements
    store_id = order_data['channel']
    subsidiary_id = get_subsidiary_id_for_web()

    locations = params.get_newstore_to_netsuite_locations_config()

    email = order_event['customer_email']
    address = get_order_billing_address(order_data)

    LOGGER.info(f'Got NST consumer: {consumer}')

    customer_custom_field_list = []

    if order_event['channel_type'] == 'web':
        customer_custom_field_list += [
            SelectCustomFieldRef(
                scriptId='custentity_nws_profilesource',
                value=ListOrRecordRef(internalId=str(
                    params.get_newstore_to_netsuite_channel_config()['web']))
            ),
            SelectCustomFieldRef(
                scriptId='custentity_nws_storecreatedby',
                value=ListOrRecordRef(internalId=params.get_netsuite_config()[
                    'shopify_location_id'])
            )
        ]

        # Get the customer data from the consumer or the address
        if address:
            first_name = address['firstName']
            last_name = address['lastName']
            phone_number = address['phone']
        elif consumer:
            first_name = consumer.get('first_name', '-')
            last_name = consumer.get('last_name', '-')
            phone_number = consumer.get('phone_number')

        first_name = remove_incompatible_chars(first_name)
        last_name = remove_incompatible_chars(last_name)

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
        subsidiary_id = get_subsidiary_id_for_store(store_id)
        if store_id in locations:
            customer_custom_field_list.append(
                SelectCustomFieldRef(
                    scriptId='custentity_nws_profilesource',
                    value=ListOrRecordRef(
                        internalId=params.get_newstore_to_netsuite_channel_config()['store'])
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
            LOGGER.error(
                f'Store id where the consumer was created {store_id} isn\'t mapped to NetSuite')

        if email and (consumer or address):
            # Get the customer data from the consumer or the address
            if consumer:
                first_name = consumer.get('first_name', '-')
                last_name = consumer.get('last_name', '-')
                phone_number = consumer.get('phone_number')
            elif address:
                first_name = address['firstName']
                last_name = address['lastName']
                phone_number = address['phone']

            first_name = remove_incompatible_chars(first_name)
            last_name = remove_incompatible_chars(last_name)

            # Generate the netsuite customer using the above data
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
            # If store exists in mapping, default customer for store - a customer is required in Netsuite
            # for each sales order
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

    # Set the tax item id if required
    tax_item_id = TaxManager.get_customer_tax_item_id(order_data['currency'])
    if tax_item_id != -1:
        netsuite_customer['taxItem'] = RecordRef(internalId=tax_item_id)

    # If customer is found we update it, but only if it is the same subsidiary
    netsuite_customer_internal_id = lookup_customer_id_by_email(
        netsuite_customer)
    if netsuite_customer_internal_id:
        LOGGER.info('Customer exists, updating the customer.')
        netsuite_customer['internalId'] = netsuite_customer_internal_id
        update_customer(netsuite_customer)
        return netsuite_customer_internal_id

    LOGGER.info('Creating new Customer.')
    # This returns the Customer or None if there is any error
    result = create_customer(netsuite_customer)
    if not result:
        raise Exception(
            f'Error on creating Customer. Customer not created. {result}')

    return result['internalId']


def get_payment_transactions(order_data):
    return order_data['paymentAccount']['transactions']['nodes']


def get_payment_items(order_event, order_data, location):
    LOGGER.info('Mapping payment items')
    # subsidiary_id = get_subsidiary_id_for_web()

    payment_items = []
    if order_data['paymentAccount'] is None:
        return payment_items

    is_exchange_order = order_data['isExchange']
    transactions = get_payment_transactions(order_data)

    for transaction in transactions:
        method = transaction['instrument']['paymentMethod'].lower()
        provider = transaction['instrument']['paymentProvider'].lower()
        currency = transaction['currency'].lower()

        # Exchange is not supported
        if is_exchange_order:
            raise ValueError(
                'Order is flagged as exchange but web exchanges are not supported.')

        if method == 'credit_card':
            payment_config = params.get_newstore_to_netsuite_payment_items_config()[
                method].get(provider, {})
            if isinstance(payment_config, numbers.Number):
                payment_item_id = payment_config
            else:
                payment_item_id = payment_config.get(currency, '')
        elif method == 'gift_card':
            payment_item_id = params.get_newstore_to_netsuite_payment_items_config().get(
                method, {}).get(currency, '')
        else:
            payment_config = params.get_newstore_to_netsuite_payment_items_config().get(method, {})
            if isinstance(payment_config, numbers.Number):
                payment_item_id = payment_config
            else:
                payment_item_id = payment_config.get(currency, '')

        # In case the payment item isn't mapped and the order is WEB utilize Shopify payment item as default
        if not payment_item_id and order_event['channel_type'] == 'web':
            payment_item_id = params.get_newstore_to_netsuite_payment_items_config().get(
                'shopify', {}).get(currency, '')

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
                'taxCode': params.RecordRef(internalId=TaxManager.get_order_payment_item_tax_code_id(currency)),
                'location': location
            }

            payment_items.append(payment_item)
            LOGGER.info(
                f'Payment Item for payment method {method} added to items.')

    return payment_items


# Creates the Netsuite Sales order out of a NewStore order
def get_sales_order(order_event, order_data):  # pylint: disable=W0613
    for item in order_event['items']:
        # Get a service level which is not IN_STORE_HANDOVER for mixed orders
        if item.get('shipping_service_level', None) != 'IN_STORE_HANDOVER':
            service_level = item.get('shipping_service_level', None)

    logging.info(f'service level is {service_level}')

    if service_level in params.get_newstore_to_netsuite_shipping_methods_config():
        shipping_method_id = params.get_newstore_to_netsuite_shipping_methods_config()[
            service_level]
    else:
        raise Exception(
            f'Shipping service_level {service_level} is not mapped to NetSuite. Update the mapping to include it.')

    # Map dates and other header fields
    placed_at_string = order_event['placed_at']
    tran_date = datetime.strptime(
        placed_at_string[:22], '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=timezone.utc)
    tran_date = tran_date.astimezone(pytz.timezone(
        params.get_netsuite_config().get('NETSUITE_DATE_TIMEZONE', 'US/Eastern')))

    currency = order_event['currency']
    currency_id = params.get_currency_id(currency_code=currency)
    partner_id = int(params.get_netsuite_config()[
        'newstore_partner_internal_id'])

    # Get Subsidiary id based on the store or DC
    store_id = order_event['channel']
    subsidiary_id = get_subsidiary_id_for_web()

    if order_event['channel_type'] == 'web':
        location_id = params.get_netsuite_config()['shopify_location_id']
        selling_location_id = params.get_netsuite_config().get(
            'shopify_selling_location_id', {}).get(currency.lower(), '')
        department_id = params.get_netsuite_config()['web_department_id']

    elif store_id in params.get_newstore_to_netsuite_locations_config():
        locations = params.get_newstore_to_netsuite_locations_config()
        location_id = locations.get(store_id)['id']
        selling_location_id = locations.get(store_id)['selling_id']
        department_id = params.get_netsuite_config()['store_department_id']
        subsidiary_id = get_subsidiary_id_for_store(store_id)
    else:
        raise Exception(f'Location {store_id} cannot be identified.')

    if order_event['shipping_total'] > 0:
        ship_tax = round(order_event['shipping_tax']
                         * 100 / order_event['shipping_total'], 4)
    else:
        ship_tax = 0.0

    sales_order = {
        'externalId': order_event['external_id'],
        'tranDate': tran_date.date(),
        'currency': params.RecordRef(internalId=currency_id),
        'subsidiary': params.RecordRef(internalId=subsidiary_id),
        'customForm': params.RecordRef(internalId=int(params.get_netsuite_config()['sales_order_custom_form_internal_id'])),
        'location': params.RecordRef(internalId=location_id),
        'shipMethod': params.RecordRef(internalId=shipping_method_id),
        'shippingCost': order_event['shipping_total'],
        'shippingTaxCode': params.RecordRef(internalId=TaxManager.get_shipping_tax_code_id(currency)),
        'class': params.RecordRef(internalId=selling_location_id),
        'department': params.RecordRef(internalId=department_id),
        'customFieldList': CustomFieldList([
            StringCustomFieldRef(
                scriptId='custbody_nws_shopifyorderid',
                value=order_event['external_id']
            ),
            StringCustomFieldRef(
                scriptId='custbody_ship_taxrate_override',
                value=ship_tax
            )
        ])
    }

    if partner_id > -1:
        sales_order['partner'] = params.RecordRef(internalId=partner_id)

    # If there is a shipping address, add it to the order
    shipping_address = get_order_shipping_address(order_data)
    if shipping_address:
        customer_name = ' '.join(filter(None, [shipping_address['firstName'],
                                               shipping_address['lastName']])) or '-'

        LOGGER.info(f'Get Shipping Address: {shipping_address}')

        address = {
            'country': Utils.get_countries_map().get(shipping_address['country'], '_unitedStates'),
            'state': shipping_address['state'],
            'zip': shipping_address['zipCode'],
            'city': shipping_address['city'][0:CITY_SUBSTRING_LIMIT],
            'addr1': remove_incompatible_chars(shipping_address['addressLine1']),
            'addr2': remove_incompatible_chars(shipping_address['addressLine2']),
            'addressee': remove_incompatible_chars(customer_name)
        }

        sales_order['shippingAddress'] = Address(**address)

        LOGGER.info(f'Added Shipping Address for sales order as -- {address}')

    # If there is a billing address, add it to the order
    billing_address = get_order_billing_address(order_data)
    if billing_address:
        customer_name = ' '.join(filter(None, [billing_address['firstName'],
                                               billing_address['lastName']])) or '-'

        address = {
            'country': Utils.get_countries_map().get(billing_address['country'], '_unitedStates'),
            'state': billing_address['state'],
            'zip': billing_address['zipCode'],
            'city': billing_address['city'][0:CITY_SUBSTRING_LIMIT],
            'addr1': remove_incompatible_chars(billing_address['addressLine1']),
            'addr2': remove_incompatible_chars(billing_address['addressLine2']),
            'addressee': remove_incompatible_chars(customer_name)
        }

        sales_order['billingAddress'] = Address(**address)

        LOGGER.info(f'Added Billing Address for sales order as -- {address}')

    return sales_order


def get_order_shipping_address(order):
    for addr in order['addresses']['nodes']:
        if addr['addressType'] == 'shipping':
            return addr
    return None


def get_order_billing_address(order):
    for addr in order['addresses']['nodes']:
        if addr['addressType'] == 'billing':
            return addr
    return None


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
    raise Exception(f'External Product ID not Found in NetSuite. {name}')


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
    raise Exception(
        f'Product not Found in NetSuite. {name}')


def get_sales_order_items(order_event): # pylint: disable=too-many-locals
    store_id = order_event['channel']
    # subsidiary_id = get_subsidiary_id_for_web()
    currency = order_event['currency']

    if order_event['channel_type'] == 'web':
        location_id = params.get_netsuite_config()['shopify_location_id']
    elif store_id in params.get_newstore_to_netsuite_locations_config():
        locations = params.get_newstore_to_netsuite_locations_config()
        location_id = locations.get(store_id)['id']
        # subsidiary_id = get_subsidiary_id_for_store(store_id)

    sales_order_items = []

    order_items = order_event['items']

    for item in order_items:
        item_custom_field_list = []

        netsuite_item_id = item['product_id']
        if netsuite_item_id in params.get_giftcard_product_ids_config():
            if require_shipping(item):
                netsuite_item_id = params.get_netsuite_config()[
                    'netsuite_p_gift_card_item_id']
            else:
                netsuite_item_id = params.get_netsuite_config()[
                    'netsuite_e_gift_card_item_id']
        else:
            product = get_product_by_name(netsuite_item_id)
            netsuite_item_id = product['internalId']

        # Tax is not mapped to the tax code, we get the tax rate from the details
        tax_rates = get_tax_rates(item)
        for index, tax_rate in enumerate(tax_rates):
            # Adding the custom taxes
            script_id = f"custcol_nws_tax_rate_{index+1}"
            item_custom_field_list.append(StringCustomFieldRef(
                scriptId=script_id, value=tax_rate))

        # In case the items has discounts, we need to adjust the price of the item and
        # inject some custom fields / the discount item
        has_item_discount, has_order_discount, has_discount, total_discount = Utils.get_discount_info(
            item)

        sales_order_item = {
            'item': RecordRef(internalId=netsuite_item_id),
            'price': params.RecordRef(internalId=params.CUSTOM_PRICE),
            'rate': str(item['pricebook_price']),
            # 'location': params.RecordRef(internalId=location_id),
            'taxCode': params.RecordRef(internalId=TaxManager.get_order_item_tax_code_id(currency)),
            'quantity': 1
        }

        # Set the location only for an Endless Aisle Order, but only for the items with INSTORE_HANDOVER
        # The location_id is already the one of the store
        if item.get('shipping_service_level', None) == 'IN_STORE_HANDOVER':
            sales_order_item['location'] = params.RecordRef(internalId=location_id)

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
                    'taxCode': params.RecordRef(internalId=TaxManager.get_duty_item_tax_code_id(currency))
                }
                sales_order_items.append(item_duty_charge)

            price = float(item['pricebook_price'])
            tax_rate = round(tax * 100 / price, 4)
        else:
            tax_rate = 0.0

        item_custom_field_list.append(
            StringCustomFieldRef(
                scriptId='custcol_nws_override_taxcode',
                value=tax_rate
            )
        )

        # Add a custom field for the line and order discount - needed for reporting in Netsuite
        if has_item_discount:
            item_custom_field_list.append(
                StringCustomFieldRef(
                    scriptId='custcol_fao_line_item_discount',
                    value=item['item_discounts']
                )
            )

        if has_order_discount:
            item_custom_field_list.append(
                StringCustomFieldRef(
                    scriptId='custcol_fao_order_item_discount',
                    value=item['order_discounts']
                )
            )

        if item_custom_field_list:
            sales_order_item['customFieldList'] = CustomFieldList(
                item_custom_field_list)

        sales_order_items.append(sales_order_item)

        # Send the information about the discounts in special discount items
        if has_discount:
            sales_order_items.append(
                {
                    'item': RecordRef(internalId=int(params.get_netsuite_config()['newstore_discount_item_id'])),
                    'price': params.RecordRef(internalId=params.CUSTOM_PRICE),
                    'rate': str('-'+str(total_discount)),
                    'taxCode': params.RecordRef(internalId=TaxManager.get_discount_item_tax_code_id(currency)),
                    'location': RecordRef(internalId=location_id)
                }
            )
    return sales_order_items

# Gets a potential shipping discount item from the order
def get_shipping_discount_item(order_event):
    sales_order_items = []

    # Unfortunately, there is no way to get the shipping data from the event or via
    # GraphQL, so needs a manual ugly check
    discount_total = order_event['discount_total']
    if discount_total > 0:
        store_id = order_event['channel']
        currency = order_event['currency']

        if order_event['channel_type'] == 'web':
            location_id = params.get_netsuite_config()['shopify_location_id']
        elif store_id in params.get_newstore_to_netsuite_locations_config():
            locations = params.get_newstore_to_netsuite_locations_config()
            location_id = locations.get(store_id)['id']

        # Calculate the item total + shipping we inject into Netsuite
        discount_total_items = 0

        order_items = order_event['items']
        for item in order_items:
            _, _, has_discount, total_discount = Utils.get_discount_info(item)

            if has_discount:
                discount_total_items = discount_total_items + round(total_discount, 2)

        # if the order discount total is greater than the discount for the items, there must be
        # a shipping discount
        if discount_total > discount_total_items:
            shipping_discount = round(discount_total - discount_total_items, 2)
            sales_order_items.append(
                {
                    'item': RecordRef(internalId=int(params.get_netsuite_config()['newstore_discount_item_id'])),
                    'price': params.RecordRef(internalId=params.CUSTOM_PRICE),
                    'rate': str('-'+str(shipping_discount)),
                    'taxCode': params.RecordRef(internalId=TaxManager.get_discount_item_tax_code_id(currency)),
                    'location': RecordRef(internalId=location_id)
                }
            )

    return sales_order_items

def get_subsidiary_id_for_web():
    return params.get_netsuite_config()['subsidiary_ca_internal_id']


def get_subsidiary_id_for_store(store_id):
    newstore_to_netsuite_locations = params.get_newstore_to_netsuite_locations_config()
    subsidiary_id = newstore_to_netsuite_locations.get(
        store_id, {}).get('subsidiary_id')

    if not subsidiary_id:
        raise ValueError(
            f"Unable to find subsidiary for NewStore location '{store_id}'.")
    return subsidiary_id


# Extract the tax rates (percentages) from the tax provider details
# The NewStore payload looks like that for the item:
#
# Shopify:
#
# "tax_provider_details": [{
#     "name": "CAN - QC (GST)",
#     "amount": 1.73,
#     "rate": 0.05
# }, {
#     "name": "CAN - QC (QST)",
#     "amount": 3.44,
#     "rate": 0.09975
# }],
#
# Associate App:
#
# "tax_provider_details": [{
#     "name": "CANADA GST/TPS",
#     "amount": 1.45,
#     "rate": 0.05
# }, {
#     "name": "QUEBEC QST/TVQ",
#     "amount": 2.89,
#     "rate": 0.09975
# }],
def get_tax_rates(item):
    tax_rates = []

    ca_tax_rate_1 = False
    ca_tax_rate_2 = False

    # Map Canadian taxes to the tax rates
    tax_provider_details = item.get('tax_provider_details', None)
    if tax_provider_details is not None:
        for tax_detail in tax_provider_details:
            if tax_detail['name'].find('GST') > -1 or tax_detail['name'].find('HST') > -1:
                tax_rates.append(round(tax_detail['rate'] * 100, 4))
                ca_tax_rate_1 = True

            if tax_detail['name'].find('PST') > -1 or tax_detail['name'].find('QST') > -1:
                tax_rates.append(round(tax_detail['rate'] * 100, 4))
                ca_tax_rate_2 = True

        # If no Canadian tax rates are found, get the rates from the array of details (if existing)
        if not ca_tax_rate_1 and not ca_tax_rate_2 and len(tax_provider_details) > 0:
            for tax_detail in tax_provider_details:
                tax_rate = round(tax_detail['rate'] * 100, 4)
                tax_rates.append(tax_rate)

    return tax_rates


def inject_sales_order(order_event, order_data, consumer):
    netsuite_sales_order = get_sales_order(order_event, order_data)

    customer_internal_id = get_customer_internal_id(
        order_event, order_data, consumer)
    netsuite_sales_order['entity'] = params.RecordRef(
        internalId=customer_internal_id)

    netsuite_sales_order_items = []
    sales_order_items = get_sales_order_items(order_event)
    sales_order_items += get_shipping_discount_item(order_event)
    sales_order_items += get_payment_items(order_event,
                                           order_data, netsuite_sales_order['location'])
    sales_order_items += [TaxManager.get_tax_offset_line_item(order_event['currency'])]
    for item in sales_order_items:
        netsuite_sales_order_items.append(SalesOrderItem(**item))
    netsuite_sales_order['itemList'] = SalesOrderItemList(
        netsuite_sales_order_items)

    result, sale, _ = create_salesorder(netsuite_sales_order)
    if not result:
        raise Exception(
            f'Error on creating SalesOrder. SalesOrder not created. {result}')

    LOGGER.info('SalesOrder created successfully.')
    return result, sale, sales_order_items
