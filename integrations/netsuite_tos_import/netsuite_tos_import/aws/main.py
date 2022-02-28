import os
import time
import json
import logging
import asyncio

# Runs startup processes
import netsuite.netsuite_environment_loader  # pylint: disable=W0611
import netsuite.api.sale as netsuite_sale
from netsuite.service import (
    TransactionSearchAdvanced,
    SearchPreferences,
    BooleanCustomFieldRef,
    TransferOrder,
    CustomFieldList
)
from netsuite.client import client as netsuite_client, make_passport
from newstore_adapter.exceptions import NewStoreAdapterException
from netsuite_tos_import.utils import Utils

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
SEARCH_PAGE_SIZE = os.environ.get('SEARCH_PAGE_SIZE', '50')
TRANSFER_ORDER_SAVED_SEARCH_ID = Utils.get_netsuite_config()[
    'transfer_orders_saved_search_id']
NETSUITE_SYNCED_TO_NEWSTORE_FLAG_SCRIPT_ID = Utils.get_netsuite_config()[
    'transfer_orders_processed_flag_script_id']
NEWSTORE_TO_NETSUITE_LOCATIONS = Utils.get_netsuite_location_map()


def handler(_, context):
    Utils.get_newstore_conn(context)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(import_transfer_orders())
    loop.stop()
    loop.close()
    return {
        'statusCode': 200
    }


async def import_transfer_orders():
    search_result = await run_transfer_order_ss()

    if not search_result:
        LOGGER.info('No results to process...')
        return

    if not search_result['body']['searchResult']['totalRecords']:
        LOGGER.info('No results to process, returning')
        return

    LOGGER.info(
        f"Found a total of {search_result['body']['searchResult']['totalRecords']} transfer orders")

    newstore_transfer_order_list = await transform_search_result(search_result)
    for transfer_order_payload in newstore_transfer_order_list:
        LOGGER.info(f'transfer_order_payload: {transfer_order_payload}')
        transfer_order_payload = validate_products(transfer_order_payload)
        try:
            create_transfer(transfer_order_payload['newstore_transfer'])
        except NewStoreAdapterException as nws_exc:
            if 'order_already_exists' in str(nws_exc):
                LOGGER.warning(
                    f'Transfer Order already exists in NOM, marking transfer as processed in NetSuite.')
                mark_to_imported_by_newstore(
                    transfer_order_payload['internal_id'])
            elif "missing_products" in str(nws_exc):
                find_valid_products_in_newstore(transfer_order_payload)
            else:
                LOGGER.error(
                    f'Failed to create Transfer Order: {str(nws_exc)}', exc_info=True)
        else:
            mark_to_imported_by_newstore(transfer_order_payload['internal_id'])
            LOGGER.info(
                f"Transfer Order successfully injected {json.dumps(transfer_order_payload['newstore_transfer'])}")


async def run_transfer_order_ss():
    LOGGER.info(f'Executing NetSuite search: {TRANSFER_ORDER_SAVED_SEARCH_ID}')

    search_preferences = SearchPreferences(
        bodyFieldsOnly=False,
        returnSearchColumns=True,
        pageSize=SEARCH_PAGE_SIZE
    )

    search_result = run_until_success(
        lambda: netsuite_client.service.search(
            searchRecord=TransactionSearchAdvanced(
                savedSearchScriptId=TRANSFER_ORDER_SAVED_SEARCH_ID),
            _soapheaders={
                'searchPreferences': search_preferences,
                'tokenPassport': make_passport()
            }),
        function_description='Transfer order search function')

    if search_result:
        LOGGER.info(
            f"search_result.body.totalPages:{search_result['body']['searchResult']['totalPages']}")

    return search_result


async def transform_search_result(search_result):
    netsuite_transfer_order_list = search_result['body']['searchResult']['searchRowList']['searchRow']

    transfer_list = []
    for transfer_order_abstract in netsuite_transfer_order_list:
        LOGGER.info(
            f"Processing transfer order: {transfer_order_abstract['basic']['tranId'][0]['searchValue']}")
        is_success, transfer_order = await get_transfer_order(transfer_order_abstract['basic']['tranId'][0]['searchValue'])
        if transfer_order is None:
            LOGGER.error(
                f"Failed to retrieve transaction: {transfer_order_abstract['basic']['tranId'][0]['searchValue']}")
            continue
        if not is_success:
            LOGGER.error(
                f'Failed to retrieve transfer order: {transfer_order}')
            continue

        transfer_order_payload = await transform_transfer(transfer_order)
        LOGGER.debug(
            f'Transfer Order Payload: {json.dumps(transfer_order_payload)}')

        if not transfer_order_payload:
            continue

        transfer_list.append(transfer_order_payload)

    return transfer_list


async def transform_transfer(netsuite_transfer_order):
    destination = get_location_from_netsuite_id(
        netsuite_transfer_order['transferLocation']['internalId'])
    if not destination:
        destination = get_location_from_name(
            netsuite_transfer_order['transferLocation']['name'])
        if not destination:
            LOGGER.error(f"Unknown location: {netsuite_transfer_order['transferLocation']['name']}: "
                         f"{netsuite_transfer_order['transferLocation']['internalId']}")
            return None

    from_location = get_location_from_netsuite_id(
        netsuite_transfer_order['location']['internalId'])
    if not from_location:
        from_location = get_location_from_name(
            netsuite_transfer_order['location']['name'])

    netsuite_transfer_order_id = netsuite_transfer_order['tranId']
    order_date = netsuite_transfer_order['tranDate'].isoformat()

    item_list = netsuite_transfer_order['itemList']['item']
    LOGGER.debug(f'item_list: {item_list}')
    product_list = [
        {
            "product_id": get_item_name(item['item']['name']),
            "ordered_quantity": int(item['quantity'])
        } for item in item_list
    ]

    newstore_transfer = {
        "external_ref": netsuite_transfer_order_id,
        "from_location_id": from_location,
        "to_location_id": destination,
        "order_date": order_date,
        "items": product_list
    }

    return {
        "newstore_transfer": newstore_transfer,
        # We need this to mark the order synced in NetSuite
        "internal_id": netsuite_transfer_order['internalId']
    }


def get_item_name(item_name):
    output = item_name
    item_name_list = item_name.split(' ')
    #for matrix items, selects variant id from name
    #'name': '2210304 : 2210304-002-XS The Hybrid Jogger in Black'
    #for non matrix items, selects the product id from name
    #'name' : '1940073-002 The Merino Wool Beanie in Black'
    if len(item_name_list) > 2:
        if item_name_list[2].split('-')[0].isnumeric():
            output = item_name_list[2]
        else:
            output = item_name_list[0]
    return output


def get_location_from_name(location_name):
    """
    The `from_location` is free-form in NewStore, this function simply cleans
    up the default NetSuite value and returns one similar to how the name appears
    in NetSuite:
    e.g. "US : Pixior : Pixior Retail" ==> "Pixior Retail"
    """
    location_name = location_name.split(':')[-1].strip()
    return location_name


def get_location_from_netsuite_id(netsuite_location_id):
    for newstore_location_id in NEWSTORE_TO_NETSUITE_LOCATIONS:
        if NEWSTORE_TO_NETSUITE_LOCATIONS[newstore_location_id]['id'] == int(netsuite_location_id):
            return NEWSTORE_TO_NETSUITE_LOCATIONS[newstore_location_id]['ff_node_id']
    return None


async def get_transfer_order(tran_id):
    return netsuite_sale.get_transaction_with_tran_id(tran_id)


def run_until_success(function_to_run, function_description='method', max_tries=5, seconds_between_runs=5):
    for _ in range(max_tries):
        try:
            return function_to_run()
        except Exception as e:  # pylint: disable=W0703
            LOGGER.warning(
                f'Failed running {function_description}. Error: {str(e)}', exc_info=True)
            time.sleep(seconds_between_runs)
    LOGGER.error(
        f'Made {max_tries} attempts to run {function_description} but failed to complete')


def create_transfer(newstore_transfer):
    return Utils.get_newstore_conn().create_transfer_order(newstore_transfer)


def mark_to_imported_by_newstore(internal_id):
    """
    Updates the synced to newstore flag for a transfer order
    :param internal_id: The ID of the transfer order to update
    """
    newstore_synced_field = BooleanCustomFieldRef()
    newstore_synced_field.scriptId = NETSUITE_SYNCED_TO_NEWSTORE_FLAG_SCRIPT_ID
    newstore_synced_field.value = True

    transfer_order = TransferOrder(
        internalId=internal_id,
        customFieldList=CustomFieldList([newstore_synced_field])
    )

    response = netsuite_client.service.update(transfer_order,
                                              _soapheaders={
                                                  'tokenPassport': make_passport()
                                              })
    if response.body.writeResponse.status.isSuccess:
        LOGGER.info(
            f'Marked transfer order with id "{internal_id}" as imported by NewStore in Netsuite.')
    else:
        LOGGER.error(
            f'Failed to mark transfer order {internal_id} as synced: {response.body}')

def validate_products(transfer_order_payload):
    valid = []
    invalid = []
    for item in transfer_order_payload["newstore_transfer"]["items"]:
        if len(item["product_id"]) >= 6 and item["product_id"][:6].isnumeric():
            valid.append(item)
            LOGGER.info(f'{item["product_id"]} is valid')
        else:
            invalid.append(item["product_id"])
            LOGGER.info(f'{item["product_id"]} is invalid')

    LOGGER.info(f'INVALID product_ids removed from transfer order: {invalid}')
    transfer_order_payload['newstore_transfer']["items"] = valid
    LOGGER.info(f'Updated transfer order payload after sku validation: {transfer_order_payload}')
    return transfer_order_payload

def find_valid_products_in_newstore(transfer_order_payload):
    valid = []
    invalid = []
    for item in transfer_order_payload['newstore_transfer']["items"]:
        try:
            response = Utils.get_newstore_conn().find_product('sku', item["product_id"], "storefront-catalog-en", "en-US", {})
            LOGGER.info(f'GET product response: {response}')
            if response is None:
                invalid.append(item)
            else:
                valid.append(item)
        except NewStoreAdapterException as nws_exc:
            invalid.append(item["product_id"])
    LOGGER.info(f'INVALID: Product ids not found in NewStore and removed from transfer order: {invalid}')

    transfer_order_payload['newstore_transfer']["items"] = valid
    LOGGER.info(f'creating transfer: {transfer_order_payload["newstore_transfer"]}')
    try:
        create_transfer(transfer_order_payload['newstore_transfer'])
    except NewStoreAdapterException as nws_exc:
        LOGGER.error(
            f'Failed to create Transfer Order after validating in NewStore: {str(nws_exc)}', exc_info=True)
    else:
        mark_to_imported_by_newstore(transfer_order_payload['internal_id'])
        LOGGER.info(
            f"Transfer Order successfully injected {json.dumps(transfer_order_payload['newstore_transfer'])}")
