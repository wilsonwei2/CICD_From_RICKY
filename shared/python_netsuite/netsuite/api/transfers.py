from netsuite.client import client, passport, app_info, make_passport
from netsuite.service import (
    ItemReceipt,
    TransactionSearchBasic,
    SearchStringField,
    SearchEnumMultiSelectField,
    InventoryAdjustment,
    InventoryTransfer
)
from netsuite.utils import (
    get_record_by_type,
    format_error_message,
    search_records_using,
)
import logging
import os

logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)


def get_transfer_order(tranId):
    transaction_search = TransactionSearchBasic(
        tranId=SearchStringField(
            searchValue=tranId,
            operator='is'
        ),
        type=SearchEnumMultiSelectField(
            searchValue=['transferOrder'],
            operator='anyOf'
        )
    )
    result = search_records_using(transaction_search)
    r = result.body.searchResult
    if r.status.isSuccess:
        # The search can return nothing, meaning the transaction doesn't exist
        if r.recordList:
            return r.recordList.record[0]
    return None


def get_item_receipt(internal_id):
    return get_record_by_type('itemReceipt', internal_id)


def get_inventory_adjustment(internal_id):
    return get_record_by_type('inventoryAdjustment', internal_id)


def get_inventory_transfer(internal_id):
    return get_record_by_type('inventoryTransfer', internal_id)


def create_item_receipt(item_receipt_data):
    item_receipt = ItemReceipt(**item_receipt_data)

    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.add(item_receipt, _soapheaders={
            'tokenPassport': make_passport(),
        })
    else:
        response = client.service.add(item_receipt, _soapheaders={
            'passport': passport,
            'applicationInfo': app_info
        })

    r = response.body.writeResponse
    if r.status.isSuccess:
        internal_id = r.baseRef.internalId
        created_item_receipt = get_item_receipt(internal_id)
        return True, created_item_receipt
    return False, format_error_message(r.status.statusDetail)


def create_inventory_adjustment(inventory_adjustment_data):
    inventory_adjustment = InventoryAdjustment(**inventory_adjustment_data)

    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.add(inventory_adjustment, _soapheaders={
            'tokenPassport': make_passport(),
        })
    else:
        response = client.service.add(inventory_adjustment, _soapheaders={
            'passport': passport,
            'applicationInfo': app_info
        })

    r = response.body.writeResponse
    if r.status.isSuccess:
        internal_id = r.baseRef.internalId
        created_inventory_adjustment = get_inventory_adjustment(internal_id)
        return True, created_inventory_adjustment
    return False, format_error_message(r.status.statusDetail)


def create_inventory_transfer(inventory_transfer_data):
    inventory_transfer = InventoryTransfer(**inventory_transfer_data)

    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.add(inventory_transfer, _soapheaders={
            'tokenPassport': make_passport(),
        })
    else:
        response = client.service.add(inventory_transfer, _soapheaders={
            'passport': passport,
            'applicationInfo': app_info
        })

    r = response.body.writeResponse
    if r.status.isSuccess:
        internal_id = r.baseRef.internalId
        created_inventory_transfer = get_inventory_transfer(internal_id)
        return True, created_inventory_transfer
    return False, format_error_message(r.status.statusDetail)
