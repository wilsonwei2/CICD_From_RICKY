from netsuite.client import client, passport, app_info, make_passport

from netsuite.service import (
    CashSale,
    CashSaleItem,
    CashSaleItemList,
    SalesOrder,
    SalesOrderItem,
    SalesOrderItemList,
    RecordRef,
    SearchStringField,
    TransactionSearchBasic,
    SearchEnumMultiSelectField,
    Invoice,
    SearchMultiSelectField,
    ItemFulfillment,
    InitializeRef,
    InitializeRecord,
    SearchCustomFieldList,
    SearchStringCustomField,
    Preferences
)
from netsuite.utils import (
    get_record_by_type,
    search_records_using,
    format_error_message
)
from collections.abc import Mapping
import logging
import os

logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)


def get_item_reference(item):
    return RecordRef(
        internalId=item.internal_id,
        type='inventoryItem'
    )


def create_cashsale_salesorder(data, sale_models):
    sale = sale_models['sale'](**data)

    logger.info('sale - data xml send to Netsuite')
    logger.info(sale)

    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.add(sale, _soapheaders={
            'tokenPassport': make_passport(),
        })
    else:
        response = client.service.add(sale, _soapheaders={
            'passport': passport,
            'applicationInfo': app_info
        })


    logger.info(f'create_cashsale_salesorder - sale - xml - object - client: {client}')
    logger.info(f'Response - create_cashsale_salesorder: {response}')

    status_detail = response['body']['writeResponse']['status']['statusDetail']
    logger.info(f'response.body.statusDetail - 1: {status_detail}')

    if len(status_detail) > 0:
        code_detail = status_detail[0]['code']
        logger.info('code_detail %s', code_detail)
    else:
        code_detail = ''
    message_duplicate = code_detail

    r = response.body.writeResponse
    if r.status.isSuccess:
        record_type = None
        flag_duplicate = 0
        if sale_models['sale'] == SalesOrder:
            record_type = 'salesOrder'
        else:
            record_type = 'cashSale'
        try:
            result = get_record_by_type(record_type, r.baseRef.internalId)
        except Exception:
            logger.info('Error when retrieving created %s. '
                        'But since it was created, process should not be stoped.' % (record_type))
            return True, int(r.baseRef.internalId), flag_duplicate
        return True, result, flag_duplicate
    elif message_duplicate == 'DUP_RCRD':
        logger.info("Manage the duplicate Insert Case in Netsuite")
        record_type = None
        default_id = 1
        flag_duplicate = 1

        if sale_models['sale'] == SalesOrder:
            record_type = 'salesOrder'
            sales_order = get_sales_order(data['externalId'])
            if sales_order is not None:
                default_id = sales_order['internalId']
        else:
            record_type = 'cashSale'

        return True, default_id, flag_duplicate
    else:
        raise Exception(format_error_message(r.status.statusDetail))


def create_cashsale(data):
    sale_models = {
        'sale': CashSale,
        'item': CashSaleItem,
        'item_list': CashSaleItemList
    }
    return create_cashsale_salesorder(data, sale_models)


def create_salesorder(data):
    sale_models = {
        'sale': SalesOrder,
        'item': SalesOrderItem,
        'item_list': SalesOrderItemList
    }
    return create_cashsale_salesorder(data, sale_models)


def get_cash_sale(externalId):
    return get_transaction(externalId, '_cashSale')


def get_sales_order(externalId):
    return get_transaction(externalId, '_salesOrder')


def get_sales_order_list(external_id_list, page_size=80):
    return get_transaction_list(external_id_list, '_salesOrder', page_size)


def get_invoice_for_sales_order(createdFromInternalId):
    return get_transaction_with_created_from_id(createdFromInternalId, '_invoice')


def get_item_fulfillment(createdFromInternalId):
    return get_transaction_with_created_from_id(createdFromInternalId, '_itemFulfillment')


def get_item_fulfillment_list(createdFromInternalId):
    return get_transaction_with_created_from_id(createdFromInternalId, '_itemFulfillment', True)


def get_return_authorizations(createdFromInternalId):
    return get_transaction_with_created_from_id(createdFromInternalId, '_returnAuthorization', True)


def get_return_authorizations(createdFromInternalId):
    return get_transaction_with_created_from_id(createdFromInternalId, '_returnAuthorization', True)


"""
Return the item fulfillment information based on the tranId
"""
def get_transaction_with_tran_id(tran_id, listing=False):

    tran_id_string = str(tran_id)
    logger.info(f"sale - tran_id_string {tran_id_string}")

    transaction_search = TransactionSearchBasic(
        tranId=SearchStringField(
            searchValue=tran_id_string,
            operator='is'
        )
    )
    result = search_records_using(transaction_search)
    r = result.body.searchResult

    logger.info(f"sale - tran_id {tran_id} get_transaction_with_tran_id - search result {r}")

    if r.status.isSuccess:
        # The search can return nothing, meaning the transaction doesn't exist
        if r.recordList:
            if listing:
                return True, r.recordList.record
            else:
                return True, r.recordList.record[0]
        return True, None
    return False, r
    # Returns if the search was successful and the record if any, or nothing.



def get_transaction_with_created_from_id(createdFromInternalId, transactionType, listing=False):
    transaction_search = TransactionSearchBasic(
        createdFrom=SearchMultiSelectField(
            searchValue=[RecordRef(internalId=createdFromInternalId)],
            operator='anyOf'
        ),
        type=SearchEnumMultiSelectField(
            searchValue=[transactionType],
            operator='anyOf'
        )
    )
    result = search_records_using(transaction_search)
    r = result.body.searchResult
    if r.status.isSuccess:
        # The search can return nothing, meaning the transaction doesn't exist
        if r.recordList:
            if listing:
                return True, r.recordList.record
            else:
                return True, r.recordList.record[0]
        return True, None
    return False, r
    # Returns if the search was successful and the record if any, or nothing.


def get_transaction_with_custom_field(value, custom_field, transaction_type):
    transaction_search = TransactionSearchBasic(
        customFieldList=SearchCustomFieldList(
            SearchStringCustomField(
                operator='is',
                searchValue=value,
                scriptId=custom_field
            )
        ),
        type=SearchEnumMultiSelectField(
            searchValue=[transaction_type],
            operator='anyOf'
        )
    )
    result = search_records_using(transaction_search)
    r = result.body.searchResult
    if r.status.isSuccess:
        # The search can return nothing, meaning the transaction doesn't exist
        if r.recordList:
            return True, r.recordList.record[0]
        return True, None
    return False, None


def get_transaction(externalId, transactionType):
    transaction_search = TransactionSearchBasic(
        externalIdString=SearchStringField(
            searchValue=externalId,
            operator='is'
        ),
        type=SearchEnumMultiSelectField(
            searchValue=[transactionType],
            operator='anyOf'
        )
    )
    result = search_records_using(transaction_search)

    logger.info(f'get_transaction searching for: \n{transaction_search}')
    logger.info(f'get_transaction result: \n{result}')

    r = result.body.searchResult
    if r.status.isSuccess:
        # The search can return nothing, meaning the transaction doesn't exist
        if r.recordList:
            return r.recordList.record[0]
    return None


def get_transaction_list(external_id_list, transactionType, page_size=80):
    transaction_search = TransactionSearchBasic(
        externalId=SearchMultiSelectField(
            searchValue=[RecordRef(internalId=ext_id) for ext_id in external_id_list],
            operator='anyOf'
        ),
        type=SearchEnumMultiSelectField(
            searchValue=[transactionType],
            operator='anyOf'
        )
    )
    result = search_records_using(transaction_search, page_size)
    r = result.body.searchResult

    logger.debug(f"get_transaction_list response: {r}")

    if r.status.isSuccess:
        # The search can return nothing, meaning the transaction doesn't exist
        if r.recordList:
            return r.recordList.record
    logger.warning(f"Couldn't retrieve transaction list, response: {r}")
    return None


def create_invoice(data):
    invoice = Invoice(**data) if isinstance(data, Mapping) else data

    logger.info(f'invoice - data xml send to Netsuite - \n{invoice}')

    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.add(invoice, _soapheaders={
            'tokenPassport': make_passport(),
            'preferences': Preferences(
                warningAsError=False,
                ignoreReadOnlyFields=True
            )
        })
    else:
        response = client.service.add(invoice, _soapheaders={
            'passport': passport,
            'applicationInfo': app_info,
            'preferences': Preferences(
                warningAsError=False,
                ignoreReadOnlyFields=True
            )
        })

    logger.info(f'Response - create_invoice: {response}')

    r = response.body.writeResponse
    if r.status.isSuccess:
        return r.baseRef.internalId
    else:
        raise Exception(format_error_message(r.status.statusDetail))


def create_item_fulfillment(data):
    item_fulfillment = ItemFulfillment(**data) if isinstance(data, Mapping) else data

    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.add(item_fulfillment, _soapheaders={
            'tokenPassport': make_passport()
        })
    else:
        response = client.service.add(item_fulfillment, _soapheaders={
            'passport': passport,
            'applicationInfo': app_info
        })

    r = response.body.writeResponse
    if r.status.isSuccess:
        return r.baseRef.internalId
    else:
        raise Exception(format_error_message(r.status.statusDetail))


def initialize_record(record_type, reference_type, reference_internal_id):
    reference = {
        'type': reference_type,
        'internalId': reference_internal_id
    }
    record = InitializeRecord(
        type=record_type,
        reference=InitializeRef(**reference)
    )


    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.initialize(
                record,
                _soapheaders={'tokenPassport': make_passport()}
            )
    else:
        response = client.service.initialize(
                record,
                _soapheaders={'passport': passport, 'applicationInfo': app_info}
            )


    r = response.body.readResponse
    if r.status.isSuccess:
        return r.record
    else:
        logger.info("%s - not able to initialize" % record_type)
        logger.info(response)
        return None


def update_sales_order(sales_order_data):
    sales_order = SalesOrder(**sales_order_data) if isinstance(sales_order_data, Mapping) else sales_order_data
    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.update(sales_order, _soapheaders={
            'tokenPassport': make_passport()
        })
    else:
        response = client.service.update(sales_order, _soapheaders={
            'passport': passport,
            'applicationInfo': app_info
        })

    r = response.body.writeResponse
    if r.status.isSuccess:
        internal_id = r.baseRef.internalId
        return True, get_record_by_type('salesOrder', internal_id)
    else:
        return False, format_error_message(r.status.statusDetail)


def upsert_list(records):
    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.upsertList(
                records,
                _soapheaders={
                    'tokenPassport': make_passport(),
                    'preferences': Preferences(
                        warningAsError=False,
                        ignoreReadOnlyFields=True
                    )
                }
            )
    else:
        response = client.service.upsertList(
                records,
                _soapheaders={
                    'passport': passport,
                    'applicationInfo': app_info,
                    'preferences': Preferences(
                        warningAsError=False,
                        ignoreReadOnlyFields=True
                    )
                }
            )

    logger.info(f'Response - upsert_list: {response}')

    r = response.body.writeResponseList.writeResponse[0]
    if r.status.isSuccess:
        return True
    else:
        logger.warning("Not able to upsertList.")
        logger.info(response)
        return None
