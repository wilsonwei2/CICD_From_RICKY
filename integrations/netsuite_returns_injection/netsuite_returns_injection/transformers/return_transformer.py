import logging
import numbers

from netsuite_returns_injection.helpers.utils import Utils
from netsuite.api.item import get_product_by_name
from netsuite.service import (
    RecordRef,
    CashRefundItem,
    CreditMemoItem,
    CustomFieldList,
    StringCustomFieldRef,
    BooleanCustomFieldRef
)

NETSUITE_CONFIG = Utils.get_netsuite_config()
NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS = Utils.get_nws_to_netsuite_payment()
LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)


async def map_payment_items(payment_instrument_list, ns_return, store_tz, subsidiary_id, location_id=None, is_credit_memo=False):  # pylint: disable=too-many-arguments
    refund_transactions = await _get_refund_transactions(payment_instrument_list=payment_instrument_list,
                                                         ns_return=ns_return,
                                                         store_tz=store_tz)

    payment_items = await _get_payment_items(refund_transactions=refund_transactions,
                                             payment_instrument_list=payment_instrument_list,
                                             subsidiary_id=subsidiary_id,
                                             ns_return=ns_return,
                                             location_id=location_id,
                                             is_credit_memo=is_credit_memo)
    return payment_items, refund_transactions


async def _get_payment_items(refund_transactions, payment_instrument_list, subsidiary_id, ns_return, location_id=None, is_credit_memo=False):  # pylint: disable=too-many-arguments
    payment_items = []
    for refund_transaction in refund_transactions:
        payment_method = refund_transaction['payment_method']
        payment_provider = refund_transaction['payment_provider']
        currency = payment_instrument_list[0]['currency'].lower()
        LOGGER.info(f'transform_order - payment_method {payment_method} - payment_provider {payment_provider}')

        if payment_method == 'credit_card':
            payment_item_id = _get_payment_item_id(payment_method, payment_provider, currency)
        elif payment_method == 'gift_card':
            payment_item_id = NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS.get(payment_method, {}).get(currency, '')
        else:
            payment_item_id = _get_payment_item_id(payment_method, None, currency)

        if payment_item_id:
            if location_id is not None:
                location_ref = RecordRef(internalId=location_id)
            else:
                return_location_id = ns_return['return_location_id']
                item_location_id = Utils.get_netsuite_store_internal_id(return_location_id, True)
                location_ref = RecordRef(internalId=item_location_id)

            amount = _get_amount(refund_transaction)
            payment_item = {
                'item': RecordRef(internalId=payment_item_id),
                'amount': amount,
                'taxCode': RecordRef(internalId=Utils.get_not_taxable_id(subsidiary_id=subsidiary_id)),
                'location': location_ref
            }
            LOGGER.info(f'Payment item: {payment_item}')

            if payment_method == 'gift_card':
                gc_code = _get_gc_code(refund_transaction)
                payment_item['customFieldList'] = CustomFieldList([
                    StringCustomFieldRef(scriptId='custcol_nws_gcnumber', value=gc_code)
                ])

            if is_credit_memo:
                payment_items.append(CreditMemoItem(**payment_item))
            else:
                payment_items.append(CashRefundItem(**payment_item))

            LOGGER.info(f'Payment Item for payment method {payment_method} added to items.')
        else:
            err_msg = f'Payment Item for payment method {payment_method} not mapped.'
            # If payment was not mapped it should throw error so that we know about it
            # It can't be injected on NetSuite with the payment item not mapped accordingly
            raise ValueError(err_msg)
    return payment_items


def _get_payment_item_id(payment_method, payment_provider, currency):
    payment_item_id = None
    payment_config = {}
    if payment_provider:
        payment_config = NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS[payment_method].get(payment_provider, {})
    else:
        payment_config = NEWSTORE_TO_NETSUITE_PAYMENT_ITEMS.get(payment_method, {})
    if isinstance(payment_config, numbers.Number):
        payment_item_id = payment_config
    else:
        payment_item_id = payment_config.get(currency, '')

    return payment_item_id

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


async def _get_refund_transactions(payment_instrument_list, ns_return, store_tz):
    refund_transactions = []
    for instrument in payment_instrument_list:
        for original_transaction in instrument['original_transactions']:
            date_string = Utils.get_one_of_these_fields(ns_return, ['returned_at', 'requested_at'])
            returned_at = Utils.format_datestring_for_netsuite(date_string=date_string,
                                                               time_zone=store_tz)
            if original_transaction['created_at']:
                transaction_created_at = Utils.format_datestring_for_netsuite(date_string=original_transaction['created_at'],
                                                                              time_zone=store_tz)
                diff_seconds = (transaction_created_at - returned_at).total_seconds()
                LOGGER.info(f'Issue refund diff_seconds: {diff_seconds}')
            else:
                LOGGER.warning(f'original_transaction {original_transaction["transaction_id"]} does not have created_at datetime')
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


async def map_cash_refund_items(customer_order, ns_return, subsidiary_id, location_id=None):
    cash_refund_items = []
    returned_order_line_ids = [item['id'] for item in ns_return['items']]
    sellable = [item['product_id']
                for item in ns_return['items']
                if item.get('item_condition') == 'Sellable' or item.get('condition_code') == 1]
    for item in customer_order['products']:
        if item['status'] != 'returned' or item['sales_order_item_uuid'] not in returned_order_line_ids:
            continue

        item_custom_field_list = [
            # Mark as damaged if item is damaged ML-183
            BooleanCustomFieldRef(
                scriptId='custcol_adj_for_damages',
                value=item['id'] not in sellable
            )
        ]
        netsuite_item_id = get_netsuite_item_id(item, item_custom_field_list, customer_order)

        cash_refund_item = {
            'item': RecordRef(
                internalId=netsuite_item_id,
                type='inventoryItem'
            ),
            'price': RecordRef(internalId=-1),
            'rate': str(item['price_catalog']),
            'taxCode': RecordRef(internalId=Utils.get_not_taxable_id(subsidiary_id=subsidiary_id))
        }

        if location_id is not None:
            cash_refund_item['location'] = RecordRef(internalId=location_id)
        else:
            return_location_id = ns_return['return_location_id']
            is_sellable = item['id'] in sellable
            if not is_sellable:
                LOGGER.info("Item cannot be resold, sending to store's damage location")
            else:
                sellable.remove(item['id'])
            item_location_id = Utils.get_netsuite_store_internal_id(return_location_id, is_sellable)
            if not item_location_id:
                raise Exception(f"Returned_from store {return_location_id} isn't mapped to NetSuite")
            cash_refund_item['location'] = RecordRef(internalId=item_location_id)

        if item['price_tax'] > 0:
            tax_rate = calcule_tax(item['price_catalog'], item['price_tax'])
            cash_refund_item['taxCode'] = RecordRef(internalId=Utils.get_tax_code_id(subsidiary_id=subsidiary_id))
            item_custom_field_list.append(
                StringCustomFieldRef(
                    scriptId='custcol_taxrateoverride',
                    value=tax_rate
                )
            )

        if item_custom_field_list:
            cash_refund_item['customFieldList'] = CustomFieldList(item_custom_field_list)

        cash_refund_items.append(cash_refund_item)

        if len(item['discounts']) > 0:
            coupon_code = item['discounts'][0]['coupon_code']
            if coupon_code:
                item_custom_field_list.append(
                    StringCustomFieldRef(
                        scriptId='custcol_nws_promocode',
                        value=coupon_code
                    )
                )

            price_adjustment_refund_item = {
                'item': RecordRef(internalId=int(NETSUITE_CONFIG['shopify_discount_item_id'])),
                'price': RecordRef(internalId=-1),
                'rate': str('-' + str(abs(item['discounts'][0]['price_adjustment']))),
                'location': RecordRef(internalId=get_discount_location(ns_return, location_id)),
                'taxCode': RecordRef(internalId=Utils.get_not_taxable_id(subsidiary_id=subsidiary_id))
            }

            if location_id is not None:
                price_adjustment_refund_item['location'] = RecordRef(internalId=location_id)

            cash_refund_items.append(price_adjustment_refund_item)
    return cash_refund_items


def get_discount_location(ns_return, location_id):
    if location_id is not None:
        item_location_id = location_id
    else:
        return_location_id = ns_return['return_location_id']
        item_location_id = Utils.get_netsuite_store_internal_id(return_location_id, True)
    return item_location_id


def get_netsuite_item_id(item, item_custom_field_list, customer_order):
    if Utils.is_product_gift_card(item['id']):
        if Utils.require_shipping(item):
            netsuite_item_id = NETSUITE_CONFIG['netsuite_p_gift_card_item_id']
        else:
            netsuite_item_id = NETSUITE_CONFIG['netsuite_e_gift_card_item_id']
        gc_number = get_gift_card_number(item, customer_order)[-4:]
        if gc_number:
            item_custom_field_list.append(StringCustomFieldRef(scriptId='custcol_nws_gcnumber', value=gc_number))
        else:
            LOGGER.info('Serial Number for gift card not provided on the external fields.')
    else:
        netsuite_item_id = get_product_by_name(item['id'])
        if netsuite_item_id:
            netsuite_item_id = netsuite_item_id['internalId']
        else:
            raise Exception(f"Unable to fetch product internal ID from NetSuite. Product {item['id']}")
    return netsuite_item_id


def get_gift_card_number(item, customer_order):
    products = [product for product in customer_order['products']
                if item['id'] == product['sales_order_item_uuid']]

    if len(products) > 0:
        return _get_external_identifiers(products[0]['external_identifiers'], 'serial_number')

    return ''


def _get_external_identifiers(external_identifiers, key):
    result = next((item for item in external_identifiers if item['type'] == key), False)
    return '' if not result else result['value']


async def get_gc_last_digits(shopify_handler, number):
    gift_card = shopify_handler.get_gift_card(number)
    return gift_card.get('last_characters', '0000')


def calcule_tax(price, tax):
    data = tax*100/price
    return round(data, 4)


async def get_store_tz_by_customer_order(customer_order):
    if customer_order['placement_location']['id']:
        store_id = customer_order['placement_location']['id']
        store = Utils.get_newstore_conn().get_store(store_id)
        return store.get('timezone')

    if customer_order.get('products', [{}])[0].get('fulfillment_location', None):
        fulfillment_location = customer_order['products'][0]['fulfillment_location']
        if fulfillment_location in Utils.get_dc_timezone_mapping_config():
            return Utils.get_dc_timezone_mapping_config()[fulfillment_location]

    return Utils.get_dc_timezone_mapping_config()['DEFAULT']


def map_custom_fields(customer_order):
    LOGGER.info('Map custom_fields_list')
    shopify_internal_id = Utils.get_extended_attribute(customer_order['extended_attributes'], 'order_id')
    channel_type = 'mobile' if 'mobile' in customer_order['channel_type'] else customer_order['channel_type']

    custom_fields_list = [
        StringCustomFieldRef(
            scriptId='custbody_nws_ecom_orderinternalid',
            value=customer_order['sales_order_external_id']
        )
    ]

    if shopify_internal_id:
        custom_fields_list.append(
            StringCustomFieldRef(
                scriptId='custbody_nws_shopifyorderinternalid',
                value=shopify_internal_id
            )
        )

    if channel_type == 'store':
        custom_fields_list.append(
            StringCustomFieldRef(
                scriptId='custbody_nws_associateid',
                value=customer_order['associate_id']
            )
        )

    LOGGER.debug(f'custom_fields_list: {custom_fields_list}')

    return custom_fields_list
