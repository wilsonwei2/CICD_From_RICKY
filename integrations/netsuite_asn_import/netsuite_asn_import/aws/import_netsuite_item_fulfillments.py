import os
import json
import time
import logging
import asyncio

# Runs startup processes
os.environ['TENANT_NAME'] = os.environ['TENANT']
os.environ['NEWSTORE_STAGE'] = os.environ['STAGE']
import netsuite.netsuite_environment_loader # pylint: disable=W0611
import netsuite.api.sale as netsuite_sale
from netsuite.service import (
    TransactionSearchAdvanced,
    SearchPreferences,
    BooleanCustomFieldRef,
    ItemFulfillment,
    CustomFieldList
)
from netsuite.client import client as netsuite_client, make_passport
from newstore_adapter.exceptions import NewStoreAdapterException
from netsuite_asn_import.utils import Utils

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
SEARCH_PAGE_SIZE = os.environ.get('SEARCH_PAGE_SIZE', '10')
NEWSTORE_TO_NETSUITE_LOCATIONS = Utils.get_netsuite_location_map()
TRANSFER_ORDER_SAVED_SEARCH_ID = Utils.get_netsuite_config()['transfer_order_fulfillments_saved_search_id']
NETSUITE_SYNCED_TO_NEWSTORE_FLAG_SCRIPT_ID = Utils.get_netsuite_config()['item_fulfillment_processed_flag_script_id']
PHYSICAL_GC_ID = os.environ.get('PHYSICAL_GC_ID', 'PGC')
PHYSICAL_GC_SKU = os.environ.get('PHYSICAL_GC_SKU', '5500000-000')

def handler(_, context):
    # Initialize newstore conector with context
    Utils.get_newstore_conn(context)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(update_newstore_asns())
    loop.stop()
    loop.close()
    return {
        'statusCode': 200
    }


async def update_newstore_asns():
    search_result = await run_item_fulfillment_ss()

    if not search_result or not search_result['body']['searchResult']['totalRecords']:
        LOGGER.info('No results to process, returning')
        return

    LOGGER.info(f"Found a total of {search_result['body']['searchResult']['totalRecords']} item fulfillments")

    newstore_asn_list = await transform_search_result(search_result)
    for asn_payload in newstore_asn_list:
        try:
            Utils.get_newstore_conn().create_asn(asn_payload['newstore_asn'])
        except NewStoreAdapterException as nws_exc:
            if 'asn_already_exists' in str(nws_exc):
                LOGGER.warning(f'ASN already exists in NOM, marking item fulfillment as processed in NetSuite.')
                mark_imported_by_newstore(asn_payload['internal_id'])
            else:
                LOGGER.error(f"Failed to create ASN: {str(nws_exc)}", exc_info=True)
        else:
            mark_imported_by_newstore(asn_payload['internal_id'])
            LOGGER.info(f"ASN successfully injected {json.dumps(asn_payload['newstore_asn'], indent=4)}")


async def run_item_fulfillment_ss():
    LOGGER.info(f'Executing NetSuite search: {TRANSFER_ORDER_SAVED_SEARCH_ID}')

    search_preferences = SearchPreferences(
        bodyFieldsOnly=False,
        returnSearchColumns=True,
        pageSize=SEARCH_PAGE_SIZE
    )

    search_result = run_until_success(
        lambda: netsuite_client.service.search(
            searchRecord=TransactionSearchAdvanced(savedSearchScriptId=TRANSFER_ORDER_SAVED_SEARCH_ID),
            _soapheaders={
                'searchPreferences': search_preferences,
                'tokenPassport': make_passport()
            }),
        function_description="Transfer order search function")

    if search_result:
        LOGGER.info(f"search_result.body.totalPages: {search_result['body']['searchResult']['totalPages']}")
    return search_result


async def transform_search_result(search_result):
    netsuite_item_fulfillment_list = search_result['body']['searchResult']['searchRowList']['searchRow']

    asn_list = []
    for item_fulfillment_abstract in netsuite_item_fulfillment_list:
        LOGGER.info(f"Processing item fulfillment: {item_fulfillment_abstract['basic']['tranId'][0]['searchValue']}")
        is_success, item_fulfillment = await get_item_fulfillment(item_fulfillment_abstract['basic']['tranId'][0]['searchValue'])
        if not is_success:
            LOGGER.error(f'Failed to retrieve Item Fulfillment: {item_fulfillment}')
            continue
        LOGGER.info(f"retrieved netsuite Item fulfillment: {item_fulfillment}")
        asn_payload = await transform_item_fulfillment(item_fulfillment)
        LOGGER.debug(f'ASN Payload: {json.dumps(asn_payload, indent=4)}')
        if not asn_payload:
            continue
        asn_list.append(asn_payload)
    return asn_list


async def transform_item_fulfillment(netsuite_item_fulfillment):
    destination = get_newstore_location_id(netsuite_item_fulfillment['transferLocation']['internalId'])
    if not destination:
        LOGGER.error(f"Unknown location: {netsuite_item_fulfillment['transferLocation']['name']}: " \
                     f"{netsuite_item_fulfillment['transferLocation']['internalId']}")
        return None
    item_list = netsuite_item_fulfillment['itemList']['item']
    from_location = get_newstore_location_id(item_list[0]['location']['internalId'])
    netsuite_item_fulfillment_id = netsuite_item_fulfillment['tranId']
    date_shipped = netsuite_item_fulfillment['shippedDate'].isoformat()
    LOGGER.debug(f'item_list: {item_list}')

    product_list = [
        {
            "product_id": str(item['itemName']) if str(item['itemName']) != PHYSICAL_GC_SKU else PHYSICAL_GC_ID,
            "quantity": int(item['quantity'])
        } for item in item_list
    ]

    transfer_order_name = get_trans_order_name(netsuite_item_fulfillment)
    transfer_order_name_trimmed = transfer_order_name[transfer_order_name.index('#') + 1:]

    tracking_numbers = list({
        package['packageTrackingNumber']
        for package in netsuite_item_fulfillment['packageList']['package']
        if package['packageTrackingNumber']
    })
    references = [netsuite_item_fulfillment_id]
    tracking_numbers.sort()
    references.extend(list(tracking_numbers))
    shipment_ref = ' - '.join(filter(None, references))

    newstore_asn = {
        "fulfillment_node_id": destination,
        "from_location": from_location,
        "references": {
            "shipment_ref": shipment_ref[:255],
            "po_number": transfer_order_name_trimmed,
        },
        "shipment_date": date_shipped,
        "items": product_list
    }

    return {
        "newstore_asn": newstore_asn,
        "internal_id": netsuite_item_fulfillment['internalId']  # We need this to mark the order synced in NetSuite
    }


def get_newstore_location_id(netsuite_location_id):
    for newstore_location_id in NEWSTORE_TO_NETSUITE_LOCATIONS:
        if NEWSTORE_TO_NETSUITE_LOCATIONS[newstore_location_id]['id'] == int(netsuite_location_id):
            return NEWSTORE_TO_NETSUITE_LOCATIONS[newstore_location_id]['ff_node_id']
    return None


async def get_item_fulfillment(tran_id):
    return netsuite_sale.get_transaction_with_tran_id(tran_id)


def run_until_success(function_to_run, function_description='method', max_tries=5, seconds_between_runs=5):
    for _ in range(max_tries):
        try:
            return function_to_run()
        except Exception as e: # pylint: disable=W0703
            LOGGER.warning(f'Failed running {function_description}. Error: {str(e)}', exc_info=True)
            time.sleep(seconds_between_runs)
    LOGGER.error(f'Made {max_tries} attempts to run {function_description} but failed to complete')


def mark_imported_by_newstore(internal_id):
    """
    Updates the synced to newstore flag for a item fulfillment
    :param internal_id: The ID of the fulfillment item to update
    """
    newstore_synced_field = BooleanCustomFieldRef()
    newstore_synced_field.scriptId = NETSUITE_SYNCED_TO_NEWSTORE_FLAG_SCRIPT_ID
    newstore_synced_field.value = True

    item_fulfillment = ItemFulfillment(
        internalId=internal_id,
        customFieldList=CustomFieldList([newstore_synced_field])
    )

    response = netsuite_client.service.update(item_fulfillment,
                                              _soapheaders={
                                                  'tokenPassport': make_passport()
                                              })
    if response.body.writeResponse.status.isSuccess:
        LOGGER.info(f'Marked fulfillment item with id "{internal_id}" as imported by NewStore in Netsuite.')
    else:
        LOGGER.error(f'Failed to mark item fulfillment {internal_id} as synced: {response.body}')

def get_trans_order_name(item_fulfillment):
    LOGGER.debug(f"item_fulfillment: {type(item_fulfillment)}")
    #LOGGER.debug(f"item_fulfillment: {item_fulfillment}")
    try:
        custom_field_list = item_fulfillment['customFieldList']
    except KeyError:
        LOGGER.debug(f"customFieldList not found, setting name to: {item_fulfillment['createdFrom']['name']}")
        return item_fulfillment['createdFrom']['name']

    try:
        custom_fields = custom_field_list['customField']
    except KeyError:
        LOGGER.debug(f"customField not found, setting name to: {item_fulfillment['createdFrom']['name']}")
        return item_fulfillment['createdFrom']['name']

    for field in custom_fields:
        try:
            if field['scriptId'] == "custbody_gb_ordername":
                LOGGER.debug(f"Setting Transfer Order Name: {field['value']}")
                return field['value']
        except KeyError:
            continue
    LOGGER.debug(f"custbody_gb_ordername not found, setting name to: {item_fulfillment['createdFrom']['name']}")
    return item_fulfillment['createdFrom']['name']
