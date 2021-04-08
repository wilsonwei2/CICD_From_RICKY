"""
Product search
"""
from netsuite.service import (
    ItemSearchBasic,
    SearchMultiSelectField,
    SearchStringField,
    RecordRef,
    SearchBooleanField
)
from netsuite.utils import (
    get_record_by_type,
    search_records_using
)


def get_product(internal_id):
    return get_record_by_type('inventoryItem', internal_id)


def list_products(internal_ids):
    id_references = [RecordRef(internalId=id) for id in internal_ids]
    item_search = ItemSearchBasic(
        internalId=SearchMultiSelectField(
            searchValue=id_references,
            operator='anyOf'
        ))
    result = search_records_using(item_search)
    r = result.body.searchResult
    if r.status.isSuccess:
        return r.recordList.record


def get_product_by_sku(sku):
    item_search = ItemSearchBasic(
        upcCode=SearchStringField(
            searchValue=sku,
            operator='is'
        ),
        isInactive=SearchBooleanField(
            searchValue=False
        )
    )
    result = search_records_using(item_search)
    r = result.body.searchResult
    if r.status.isSuccess:
        # The search can return nothing, meaning the product doesn't exist
        if r.recordList:
            return r.recordList.record[0]
        else:
            # If the UPC code doesn't have the sku we do another search this time on the item name
            return get_product_by_name(sku)
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
    r = result.body.searchResult
    if r.status.isSuccess:
        # The search can return nothing, meaning the product doesn't exist
        if r.recordList:
            return r.recordList.record[0]
        else:
            # If the name isn't in itemId then look at external id
            return get_product_by_external_id(name)
    return None


def get_product_by_external_id(name):
    item_search = ItemSearchBasic(
        externalIdString=SearchStringField(
            searchValue=name,
            operator='is'
        ))
    result = search_records_using(item_search)
    r = result.body.searchResult
    if r.status.isSuccess:
        # The search can return nothing, meaning the product doesn't exist
        if r.recordList:
            return r.recordList.record[0]
    return None
