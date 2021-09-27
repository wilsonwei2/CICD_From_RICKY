# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.
import re
from collections.abc import Mapping
from netsuite.service import (
    RecordRef,
    CashRefundItem,
    CashRefundItemList,
    CustomFieldList,
    StringCustomFieldRef,
    SelectCustomFieldRef,
    ListOrRecordRef,
    Customer,
    CustomerCurrency,
    CustomerCurrencyList,
    CustomerAddressbook,
    CustomerAddressbookList
)
from newstore_adapter.utils import get_extended_attribute
from pom_common.netsuite import TaxManager

from netsuite_appeasement_refund_injection.helpers.utils import Utils
from netsuite_appeasement_refund_injection.helpers.utils import LOGGER

NETSUITE_CONFIG = Utils.get_netsuite_config()
NEWSTORE_TO_NETSUITE_LOCATIONS = Utils.get_netsuite_location_map()
NEWSTORE_TO_NETSUITE_CHANNEL = Utils.get_nws_to_netsuite_channel()
NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS = Utils.get_nws_to_netsuite_payment()


async def transform_online_order_refund(consumer, event_refund, customer_order, payments_info, store_tz):
    LOGGER.info('Processing online order refund')

    location_id, _, subsidiary_id = map_location(customer_order)

    LOGGER.info('Prepare countries')
    countries = Utils.get_countries()

    LOGGER.info('Map shipping address')
    shipping_address = build_shipping_address(
        customer_order['shipping_address'], countries)

    LOGGER.info('Map billing address')
    if customer_order.get('billing_address'):
        billing_address = build_billing_address(
            customer_order['billing_address'], countries)
    else:
        billing_address = None

    LOGGER.info('Map currency')
    address = customer_order['billing_address'] or customer_order['shipping_address']
    country_code = Utils.get_one_of_these_fields(params=address,
                                                 fields=['country', 'country_code'])

    currency_id = Utils.get_currency_from_country_code(
        country_code=country_code)

    LOGGER.info('Map customer')
    customer = map_customer_information(
        subsidiary_id, consumer, customer_order, billing_address, shipping_address)

    LOGGER.info('Map cash refund custom fields')
    cash_refund_custom_fields = map_cash_refund_custom_fields(customer_order)

    LOGGER.info('Map cash refund')
    cash_refund = map_cash_refund(
        subsidiary_id, event_refund, location_id, cash_refund_custom_fields, store_tz)

    LOGGER.info('Map cash refund items')
    cash_refund_item = map_cash_refund_item(event_refund, event_refund['currency'], location_id)

    LOGGER.info('Map payment items')
    payment_items, _ = await map_payment_items(payment_instrument_list=payments_info['instruments'],
                                               ns_return=event_refund,
                                               store_tz=store_tz,
                                               subsidiary_id=subsidiary_id,
                                               location_id=location_id)

    cash_refund['itemList'] = CashRefundItemList(
        cash_refund_item + payment_items)
    cash_refund['entity'] = customer
    cash_refund['currency'] = RecordRef(internalId=currency_id)

    return cash_refund


async def transform_in_store_order_refund(cash_sale, event_refund, customer_order, payments_info, store_tz):
    LOGGER.info('Processing in store order refund')

    location_id, _, subsidiary_id = map_location(customer_order)

    LOGGER.info('Map cash refund custom fields')
    cash_refund_custom_fields = map_cash_refund_custom_fields(customer_order)

    LOGGER.info('Map cash refund')
    cash_refund = map_cash_refund(
        subsidiary_id, event_refund, location_id, cash_refund_custom_fields, store_tz)

    LOGGER.info('Map cash refund items')
    cash_refund_item = map_cash_refund_item(event_refund, event_refund['currency'], location_id)

    LOGGER.info('Map payment items')
    payment_items, _ = await map_payment_items(payment_instrument_list=payments_info['instruments'],
                                               ns_return=event_refund,
                                               store_tz=store_tz,
                                               subsidiary_id=subsidiary_id,
                                               location_id=location_id)

    cash_refund['entity'] = Customer(
        internalId=cash_sale['entity']['internalId'],
        currencyList=get_currency_list()
    )
    cash_refund['createdFrom'] = RecordRef(internalId=cash_sale['internalId'])
    cash_refund['itemList'] = CashRefundItemList(
        cash_refund_item + payment_items)

    return cash_refund


def get_currency_list():
    return CustomerCurrencyList([
        CustomerCurrency(
            currency=RecordRef(internalId=int(
                Utils.get_netsuite_config()['currency_usd_internal_id']))
        ),
        CustomerCurrency(
            currency=RecordRef(internalId=int(
                Utils.get_netsuite_config()['currency_cad_internal_id']))
        ),
        CustomerCurrency(
            currency=RecordRef(internalId=int(
                Utils.get_netsuite_config()['currency_eur_internal_id']))
        )
    ])


def map_cash_refund(subsidiary_id, event_refund, location_id, cash_refund_custom_fields, store_tz):
    tran_date = Utils.format_datestring_for_netsuite(event_refund['requested_at'],
                                                     store_tz)
    cash_refund_custom_form_id = int(
        NETSUITE_CONFIG['cash_return_custom_form_internal_id'])

    partner_id = int(NETSUITE_CONFIG['newstore_partner_internal_id'])

    cash_refund = {
        'externalId': event_refund['id'],
        'tranDate': tran_date.isoformat(),
        'customForm': RecordRef(internalId=cash_refund_custom_form_id),
        'location': RecordRef(internalId=location_id),
        'discountItem': None,
        'discountRate': 0.0,
        'subsidiary': RecordRef(internalId=subsidiary_id),
        'customFieldList': CustomFieldList(cash_refund_custom_fields)
    }

    if partner_id > -1:
        cash_refund['partner'] = RecordRef(internalId=partner_id)

    return cash_refund


def map_cash_refund_item(event_refund, currency, location_id):
    return [CashRefundItem(
        item=RecordRef(
            internalId=int(
                NETSUITE_CONFIG['appeasement_refund_item_internal_id'])
        ),
        price=RecordRef(internalId=-1),
        rate=str(event_refund['amount']),
        taxCode=RecordRef(internalId=TaxManager.get_appeasement_item_tax_code_id(currency)),
        location=RecordRef(internalId=location_id)
    )]


def map_cash_refund_custom_fields(customer_order):
    shopify_internal_id = get_extended_attribute(
        customer_order['extended_attributes'], 'order_id')

    channel_type = 'mobile' if 'mobile' in customer_order[
        'channel_type'] else customer_order['channel_type']
    # if customer_order['channel_type'] in NEWSTORE_TO_NETSUITE_CHANNEL:
    #    if customer_order['channel_type'] == 'web':
    #        order_type_internal_id = NETSUITE_CONFIG['ecom_order_type_internal_id']
    #    else:
    #        order_type_internal_id = NETSUITE_CONFIG['retail_order_type_internal_id']

    custom_fields_list = [
        StringCustomFieldRef(
            scriptId='custbody_nws_shopifyorderid',
            value=customer_order['sales_order_external_id']
        ),
        StringCustomFieldRef(
            scriptId='custbody_nws_shopifyorderinternalid',
            value=shopify_internal_id
        ),
        StringCustomFieldRef(
            scriptId='custbodyaccumula_ecomid',
            value=customer_order['sales_order_external_id']
        )  # ,
        # SelectCustomFieldRef(
        #    scriptId='cseg_ab_sellingloc',
        #    value=ListOrRecordRef(internalId=selling_location_id)
        # ),
        # SelectCustomFieldRef(
        #    scriptId='custbody_ab_order_type',
        #    value=ListOrRecordRef(internalId=order_type_internal_id)
        # )
    ]

    if channel_type == 'store':
        custom_fields_list.append(
            StringCustomFieldRef(
                scriptId='custbody_nws_associateid',
                value=customer_order['associate_id']
            )
        )

    return custom_fields_list


def map_location(customer_order):
    LOGGER.info('Map location')
    channel = customer_order['placement_location']['id']
    selling_location_id = None
    if customer_order['channel_type'] == 'web':
        location_id = int(NETSUITE_CONFIG['shopify_location_id'])
        # selling_location_id = int(NETSUITE_CONFIG['shopify_selling_location_internal_id'])
        subsidiary_id = int(NETSUITE_CONFIG['subsidiary_ca_internal_id'])
    elif channel in NEWSTORE_TO_NETSUITE_LOCATIONS:
        location_id = NEWSTORE_TO_NETSUITE_LOCATIONS[channel]['id']
        # selling_location_id = NEWSTORE_TO_NETSUITE_LOCATIONS[channel]['selling_id']
        subsidiary_id = get_subsidiary_id(channel)
    else:
        raise Exception("Channel %s isn't mapped to NetSuite" % channel)

    return location_id, selling_location_id, subsidiary_id


def get_subsidiary_id(store_id):
    subsidiary_id = NEWSTORE_TO_NETSUITE_LOCATIONS.get(
        store_id, {}).get('subsidiary_id')

    if not subsidiary_id:
        raise ValueError(
            f"Unable to find subsidiary for NewStore location '{store_id}'.")
    return subsidiary_id


def map_customer_information(subsidiary_id, consumer, customer_order, billing_address, shipping_address):
    customer_custom_field_list = []

    if customer_order['channel_type'] == 'web':
        customer_custom_field_list = [
            SelectCustomFieldRef(
                scriptId='custentity_nws_profilesource',
                value=ListOrRecordRef(internalId=str(
                    NEWSTORE_TO_NETSUITE_CHANNEL['web']))
            ),
            SelectCustomFieldRef(
                scriptId='custentity_nws_storecreatedby',
                value=ListOrRecordRef(
                    internalId=NETSUITE_CONFIG['shopify_location_id'])
            )
        ]
    elif consumer:
        store_id = consumer.get('store_id', '')
        if store_id:
            customer_custom_field_list.append(
                SelectCustomFieldRef(
                    scriptId='custentity_nws_profilesource',
                    value=ListOrRecordRef(
                        internalId=NEWSTORE_TO_NETSUITE_CHANNEL['store'])
                )
            )
            if store_id in NEWSTORE_TO_NETSUITE_LOCATIONS:
                store_location_id = NEWSTORE_TO_NETSUITE_LOCATIONS[store_id]['id']
                customer_custom_field_list.append(
                    SelectCustomFieldRef(
                        scriptId='custentity_nws_storecreatedby',
                        value=ListOrRecordRef(internalId=store_location_id)
                    )
                )
            else:
                LOGGER.error(
                    f'Store id where the consumer was created {store_id} isn\'t mapped to NetSuite')

    netsuite_customer = {
        "first_name": consumer.get('first_name', '-'),
        "second_name": consumer.get('second_name', ''),
        "last_name": consumer.get('last_name', '-'),
        "phone_number": get_phone_from_object(customer_order['billing_address']),
        "email": consumer['email']
    }

    customer = build_netsuite_customer(netsuite_customer=netsuite_customer,
                                       subsidiary_id=subsidiary_id,
                                       shipping_address=shipping_address,
                                       billing_address=billing_address,
                                       custom_field_list=customer_custom_field_list)

    return customer


def build_netsuite_customer(netsuite_customer, subsidiary_id, shipping_address=None, billing_address=None, custom_field_list=None):
    first_name = netsuite_customer['first_name']
    second_name = netsuite_customer['second_name']
    last_name = netsuite_customer['last_name']
    phone_number = netsuite_customer['phone_number']
    email = netsuite_customer['email']

    customer = {
        'customForm': RecordRef(internalId=int(Utils.get_netsuite_config()['customer_custom_form_internal_id'])),
        'firstName': first_name[:32] if first_name.strip() else '-',
        'lastName': last_name[:32] if last_name.strip() else '-',
        'email': email,
        'phone': get_formated_phone(phone_number),
        'subsidiary': RecordRef(internalId=subsidiary_id),
        'isPerson': True,
        'currencyList': get_currency_list(),
        'customFieldList': custom_field_list
    }
    if second_name.strip():
        customer['middleName'] = second_name[:32]

    customer['companyName'] = re.sub(' +', ' ', ' '.join((customer['firstName'],
                                                          customer['lastName'])))

    if shipping_address or billing_address:
        if shipping_address:
            address_book = [CustomerAddressbook(**shipping_address)]
            if billing_address:
                address_book.append(CustomerAddressbook(**billing_address))
        else:
            address_book = [CustomerAddressbook(**billing_address)]

        address_book_list = {
            'replaceAll': True,
            'addressbook': address_book
        }
        customer['addressbookList'] = CustomerAddressbookList(
            **address_book_list)
    return customer


async def map_payment_items(payment_instrument_list, ns_return, store_tz, subsidiary_id, location_id=None):
    refund_transactions = await _get_refund_transactions(payment_instrument_list=payment_instrument_list,
                                                         ns_return=ns_return,
                                                         store_tz=store_tz)

    payment_items = await _get_payment_items(refund_transactions=refund_transactions,
                                             payment_instrument_list=payment_instrument_list,
                                             subsidiary_id=subsidiary_id,
                                             ns_return=ns_return,
                                             location_id=location_id)
    return payment_items, refund_transactions


async def _get_refund_transactions(payment_instrument_list, ns_return, store_tz):
    refund_transactions = []
    for instrument in payment_instrument_list:
        for original_transaction in instrument['original_transactions']:
            date_string = Utils.get_one_of_these_fields(
                ns_return, ['returned_at', 'requested_at'])
            returned_at = Utils.format_datestring_for_netsuite(date_string=date_string,
                                                               time_zone=store_tz)
            if original_transaction['created_at']:
                transaction_created_at = Utils.format_datestring_for_netsuite(date_string=original_transaction['created_at'],
                                                                              time_zone=store_tz)
                diff_seconds = (transaction_created_at -
                                returned_at).total_seconds()
                LOGGER.info(f"Issue refund diff_seconds: {diff_seconds}")
            else:
                LOGGER.warning(
                    f'original_transaction {original_transaction["transaction_id"]} does not have created_at datetime')
                diff_seconds = 1000

            # If transacion is refund or issue (store_credit) and is part of the return being processed
            if (original_transaction['reason'] == 'refund'
                    or original_transaction['reason'] == 'issue') \
                    and original_transaction['correlation_id'] == ns_return['id']:
                refund_transactions.append(original_transaction)
            elif original_transaction['reason'] == 'issue' \
                    and (original_transaction['payment_method'] == 'store_credit'
                         or original_transaction['payment_method'] == 'gift_card') \
                    and abs(diff_seconds) <= 5:
                refund_transactions.append(original_transaction)

    return refund_transactions


async def _get_payment_items(refund_transactions, payment_instrument_list, subsidiary_id, ns_return, location_id=None):
    payment_items = []
    currency = ns_return['currency']

    for refund_transaction in refund_transactions:
        payment_method = refund_transaction['payment_method']
        payment_provider = refund_transaction['payment_provider']
        payment_currency = payment_instrument_list[0]['currency'].lower()
        LOGGER.info(f"transform_order - payment_method {payment_method} - payment_provider {payment_provider} - subsidiary {subsidiary_id}")

        if payment_method == 'credit_card':
            if 'shopify' in payment_provider:
                payment_item_id = NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS[payment_method]['shopify']
            else:
                payment_item_id = NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS[payment_method]['adyen']
        elif payment_method == 'gift_card':
            payment_item_id = NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS.get(
                payment_method, {}).get(payment_currency, '')
        else:
            payment_item_id = NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS.get(
                payment_method, '')

        if payment_item_id:
            if isinstance(payment_item_id, Mapping):
                payment_item_id = payment_item_id.get(payment_currency, '')

            if location_id is not None:
                location_ref = RecordRef(internalId=location_id)
            else:
                return_location_id = ns_return['return_location_id']
                item_location_id = Utils.get_netsuite_store_internal_id(
                    return_location_id, True)
                location_ref = RecordRef(internalId=item_location_id)

            amount = _get_amount(refund_transaction)
            payment_item = {
                'item': RecordRef(internalId=payment_item_id),
                'amount': amount,
                'taxCode': RecordRef(internalId=TaxManager.get_appeasement_payment_item_tax_code_id(currency)),
                'location': location_ref
            }

            LOGGER.info(f'Payment item: {payment_item}')

            if payment_method == 'gift_card':
                gc_code = _get_gc_code(refund_transaction)
                payment_item['customFieldList'] = CustomFieldList([
                    StringCustomFieldRef(
                        scriptId='custcol_nws_gcnumber', value=gc_code)
                ])
            payment_items.append(CashRefundItem(**payment_item))
            LOGGER.info(
                f'Payment Item for payment method {payment_method} added to items.')
        else:
            err_msg = f'Payment Item for payment method {payment_method} not mapped.'
            # If payment was not mapped it should trow error so that we know about it
            # It can't be injected on NetSuite with the payment item not mapped accordingly
            raise ValueError(err_msg)
    return payment_items


def _get_amount(refund_transaction):
    if refund_transaction['reason'] == 'refund' or refund_transaction['capture_amount'] == 0:
        amount = refund_transaction['refund_amount']
    else:
        amount = refund_transaction['capture_amount']
    return amount


def _get_gc_code(refund_transaction):
    gc_number = refund_transaction['metadata'].get('number', '')
    if not gc_number:
        gc_number = refund_transaction['metadata'].get('gift_card_number', '')

    if isinstance(gc_number, int):
        # we need to call the shopify api to get the last 4 digits based on the gift card number
        gc_code = str(gc_number)[-4:]
    else:
        gc_code = gc_number[-4:]  # UntuckIT asked for the last 4 digits

    return gc_code


def build_shipping_address(address, countries):
    return build_address(address=address,
                         countries=countries,
                         is_default_shipping=True)


def build_billing_address(address, countries):
    return build_address(address=address,
                         countries=countries,
                         is_default_billing=True)


def build_address(address, countries, is_default_shipping=False, is_default_billing=False):
    country_code = Utils.get_one_of_these_fields(
        address, ['country', 'country_code'])
    addr1 = Utils.get_one_of_these_fields(
        address, ['address_line1', 'address_line_1'])
    addr2 = Utils.get_one_of_these_fields(
        address, ['address_line2', 'address_line_2'])
    addressee = ' '.join(filter(None, [address.get('first_name', '-'),
                                       address.get('second_name', ''),
                                       address.get('last_name', '')
                                       ]))
    built_address = {
        'defaultShipping': is_default_shipping,
        'defaultBilling': is_default_billing,
        'addressbookAddress': {
            'addressee': addressee,
            'country': countries[country_code],
            'addr1': addr1,
            'addr2': addr2,
            'city': address['city'],
            'state': address['state'],
            'zip': address['zip_code'],
            'addrPhone': get_phone_from_object(address)
        }
    }
    return built_address


def get_phone_from_object(object_with_phone):
    if object_with_phone.get('phone', None):
        phone = object_with_phone['phone']
    elif object_with_phone.get('contact_phone', None):
        phone = object_with_phone['contact_phone']
    else:
        for items in object_with_phone.get('addresses', []):
            phone = items.get('contact_phone', None)
            if phone:
                return phone
        phone = '5555555555'
    return get_formated_phone(phone)


def get_formated_phone(phone):
    regex = r'^\D?(\d{3})\D?\D?(\d{3})\D?(\d{4})$'
    regex_international = r'^\+?(?:[0-9] ?){6,14}[0-9]$'
    phone = phone if re.match(regex, phone) or re.match(
        regex_international, phone) else '5555555555'
    if re.match(regex, phone):
        phone = re.sub(regex, r'\1-\2-\3', phone)
    return phone
