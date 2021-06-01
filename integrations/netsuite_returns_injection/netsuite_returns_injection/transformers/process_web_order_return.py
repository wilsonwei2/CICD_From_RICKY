import os
import re
import logging
from netsuite.service import (
    RecordRef,
    CustomFieldList,
    SelectCustomFieldRef,
    ListOrRecordRef,
    CustomerCurrency,
    CustomerCurrencyList
)
from netsuite_returns_injection.transformers.return_transformer import (
    map_payment_items,
    map_cash_refund_items,
    get_store_tz_by_customer_order,
    map_custom_fields
)
from netsuite_returns_injection.helpers.utils import Utils

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)
IGNORE_REFUND_PAYMENT_MISMATCHES = bool(os.environ.get('IGNORE_REFUND_PAYMENT_MISMATCHES', False))


async def transform_web_order(customer_order, ns_return, payments_info, sales_order, return_authorization=None):
    LOGGER.info('Transform web order')
    return_location_id = ns_return['return_location_id']
    location_id = Utils.get_netsuite_store_internal_id(return_location_id)
    customer = None
    subsidiary_id = int(Utils.get_netsuite_config()['subsidiary_ca_internal_id']) if not sales_order else sales_order.subsidiary.internalId
    store_tz = await get_store_tz_by_customer_order(customer_order)
    if return_authorization:
        LOGGER.info('Create CashRefund from ReturnAuthorization')
        cash_refund = map_cash_refund(ns_return, sales_order.location.internalId, sales_order, return_authorization, store_tz)
    else:
        LOGGER.info('Create standalone CashRefund')

        if not location_id:
            raise Exception(f'Returned_from store {return_location_id} wasn\'t found')

        custom_fields_list = map_custom_fields(customer_order)
        LOGGER.debug(f'custom_fields_list: {custom_fields_list}')
        LOGGER.info('Map cash refund')
        cash_refund = map_cash_refund(ns_return, location_id, sales_order, return_authorization, store_tz)
        if custom_fields_list:
            cash_refund['customFieldList'] = CustomFieldList(custom_fields_list)
        if not sales_order:
            # Map Customer
            LOGGER.info('Map customer')
            customer = map_customer_information(customer_order, subsidiary_id)

    LOGGER.info('Map cash refund items')
    cash_refund_items = await map_cash_refund_items(customer_order, ns_return, int(subsidiary_id))
    LOGGER.info('Map payment items')
    payment_items, _ = await map_payment_items(payment_instrument_list=payments_info['instruments'],
                                               ns_return=ns_return,
                                               store_tz=store_tz,
                                               subsidiary_id=subsidiary_id)

    if not IGNORE_REFUND_PAYMENT_MISMATCHES\
            and not Utils.verify_all_payments_refunded(payment_items, ns_return['total_refund_amount']):
        LOGGER.debug(f'transform_order - payment_items {payment_items}')
        raise Exception(
            'The payments for this order were not all mapped to payments item. Verify logs for more details.')

    return {
        'customer': customer,
        'cash_refund': cash_refund,
        'cash_refund_items': cash_refund_items,
        'payment_items': payment_items
    }


def map_customer_information(customer_order, subsidiary_id):
    customer_custom_field_list = []

    customer_custom_field_list = [
        SelectCustomFieldRef(
            scriptId='custentity_nws_profilesource',
            value=ListOrRecordRef(internalId=str(Utils.get_nws_to_netsuite_channel()['web']))
        )
    ]

    email = customer_order['consumer'].get('email')

    netsuite_customer = {
        "first_name": customer_order['billing_address'].get('first_name', '-'),
        "second_name": customer_order['billing_address'].get('second_name', ''),
        "last_name": customer_order['billing_address'].get('last_name', '-'),
        "phone_number": get_phone_from_object(customer_order['billing_address'])
    }

    customer = build_netsuite_customer(netsuite_customer=netsuite_customer,
                                       email=email,
                                       subsidiary_id=subsidiary_id,
                                       custom_field_list=customer_custom_field_list,
                                       company_name=Utils.get_extended_attribute(customer_order.get('extended_attributes', []), 'organization'))
    return customer


def map_cash_refund(ns_return, location_id, sales_order, return_authorization=None, store_tz='America/New_York'):
    tran_date = Utils.format_datestring_for_netsuite(date_string=ns_return['returned_at'], time_zone=store_tz,
                                                     cutoff_index=19, format_string='%Y-%m-%dT%H:%M:%S')

    partner_id = int(Utils.get_netsuite_config()['newstore_partner_internal_id'])

    cash_refund = {
        'externalId': ns_return['id'],
        'tranDate': tran_date.date(),
        'location': RecordRef(internalId=location_id),
        'customForm': RecordRef(internalId=int(Utils.get_netsuite_config()['cash_return_custom_form_internal_id']))
    }

    if partner_id > -1:
        cash_refund['partner'] = RecordRef(internalId=partner_id)

    if sales_order:
        cash_refund['entity'] = sales_order.entity

    if return_authorization:
        cash_refund['createdFrom'] = RecordRef(internalId=return_authorization.internalId)

    return cash_refund


def _get_custom_field(fields, key):
    LOGGER.debug(f'Getting custom field {key} from: {fields}')
    for field in fields:
        if field['scriptId'] == key:
            return field
    return None


def _is_exchange_transaction(refund_transaction):
    return refund_transaction.get('metadata', {}).get('returnly_exchange', '') == 'True'


def build_netsuite_customer(netsuite_customer, email, subsidiary_id, custom_field_list=None, company_name=''):
    first_name = netsuite_customer['first_name']
    second_name = netsuite_customer['second_name']
    last_name = netsuite_customer['last_name']
    phone_number = netsuite_customer['phone_number']
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

    customer['companyName'] = company_name or re.sub(' +', ' ', ' '.join((customer['firstName'],
                                                                          customer['lastName'])))
    return customer


def get_currency_list():
    return CustomerCurrencyList([
        CustomerCurrency(
            currency=RecordRef(internalId=int(Utils.get_netsuite_config()['currency_usd_internal_id']))
        ),
        CustomerCurrency(
            currency=RecordRef(internalId=int(Utils.get_netsuite_config()['currency_gbp_internal_id']))
        ),
        CustomerCurrency(
            currency=RecordRef(internalId=int(Utils.get_netsuite_config()['currency_cad_internal_id']))
        ),
        CustomerCurrency(
            currency=RecordRef(internalId=int(Utils.get_netsuite_config()['currency_eur_internal_id']))
        )
    ])


def get_formated_phone(phone):
    regex = r'^\D?(\d{3})\D?\D?(\d{3})\D?(\d{4})$'
    regex_international = r'^\+?(?:[0-9] ?){6,14}[0-9]$'
    phone = phone if re.match(regex, phone) or re.match(regex_international, phone) else '5555555555'
    if re.match(regex, phone):
        phone = re.sub(regex, r'\1-\2-\3', phone)
    return phone


def get_phone_from_object(phone_object):
    if phone_object.get('phone', None):
        phone = phone_object['phone']
    elif phone_object.get('contact_phone', None):
        phone = phone_object['contact_phone']
    else:
        for items in phone_object.get('addresses', []):
            phone = items.get('contact_phone', None)
            if phone:
                return phone
        phone = '5555555555'
    return get_formated_phone(phone)
