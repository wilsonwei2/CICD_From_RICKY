import logging
from netsuite.service import RecordRef, CustomFieldList
from netsuite_returns_injection.transformers.return_transformer import (
    map_payment_items,
    map_cash_refund_items,
    map_custom_fields
)
from netsuite_returns_injection.helpers.utils import Utils
from netsuite_returns_injection.transformers.process_web_order_return import map_customer_information

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)


async def transform_order(cash_sale, ns_return, payments_info, customer_order=None, store_tz='America/New_York'):
    customer = None
    cash_refund = _get_cash_refund(ns_return=ns_return,
                                   cash_sale=cash_sale,
                                   store_tz=store_tz)
    subsidiary_id = int(Utils.get_netsuite_config()['subsidiary_ca_internal_id']) if not cash_sale else int(cash_sale['subsidiary']['internalId'])
    cash_refund_items = await map_cash_refund_items(customer_order,
                                                    ns_return,
                                                    subsidiary_id)
    payment_items, refund_transactions = await map_payment_items(payment_instrument_list=payments_info['instruments'],
                                                                 ns_return=ns_return,
                                                                 store_tz=store_tz,
                                                                 subsidiary_id=subsidiary_id)

    if not cash_sale:
        LOGGER.info('Create standalone CashRefund')

        custom_fields_list = map_custom_fields(customer_order)
        if custom_fields_list:
            cash_refund['customFieldList'] = CustomFieldList(custom_fields_list)

        LOGGER.info('Map customer')
        customer = map_customer_information(customer_order, subsidiary_id)

    # This verifies the transactions on NewStore
    if not Utils.verify_all_transac_refunded(refund_transactions, ns_return['total_refund_amount']):
        LOGGER.error(f'transform_order - refund_transactions {refund_transactions}')
        raise Exception('The payments for this order have not been fully refunded yet, it will only be injected upon full refund.')

    # This verifies the payment items added to the Refund
    if not Utils.verify_all_payments_refunded(payment_items, ns_return['total_refund_amount']):
        LOGGER.debug(f'transform_order - payment_items {payment_items}')
        raise Exception('The payments for this order were not all mapped to payments item. Verify logs for more details.')

    return {
        'customer': customer,
        'cash_refund': cash_refund,
        'cash_refund_items': cash_refund_items,
        'payment_items': payment_items
    }


def _get_cash_refund(ns_return, cash_sale, store_tz):
    LOGGER.info('Map CashRefund')
    # Location can be mapped using the returned_from that is the store_id on NewStore
    return_location_id = ns_return['return_location_id']
    condition = ns_return['items'][0]['item_condition']
    is_sellable = condition == 'Sellable'
    if not is_sellable:
        LOGGER.info("Item cannot be resold, sending to store's damage location")
    location_id = Utils.get_netsuite_store_internal_id(return_location_id, is_sellable)
    if not location_id:
        raise Exception(f"Return location {return_location_id} isn't mapped to NetSuite")

    tran_date = Utils.format_datestring_for_netsuite(date_string=ns_return['returned_at'],
                                                     time_zone=store_tz)

    partner_id = int(Utils.get_netsuite_config()['newstore_partner_internal_id'])

    cash_refund = {
        'externalId': ns_return['id'],
        'tranDate': tran_date.isoformat(),
        'customForm': RecordRef(internalId=int(Utils.get_netsuite_config()['cash_return_custom_form_internal_id'])),
        'location': RecordRef(internalId=location_id),
        'discountItem': None,
        'discountRate': 0.0
    }

    if partner_id > -1:
        cash_refund['partner'] = RecordRef(internalId=partner_id)

    if cash_sale:
        cash_refund['createdFrom'] = RecordRef(internalId=cash_sale['internalId'])

    return cash_refund
