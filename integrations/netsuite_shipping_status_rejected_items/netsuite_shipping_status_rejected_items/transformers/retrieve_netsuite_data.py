import os
import logging

from netsuite.service import (
    TransactionSearchAdvanced,
    BooleanCustomFieldRef,
    SalesOrder,
    CustomFieldList,
    SearchPreferences,
    RecordRef
)
from netsuite.client import client, make_passport
from netsuite_shipping_status_rejected_items.utils import Utils


LOG_LEVEL_STR = os.environ.get('LOG_LEVEL', 'INFO')
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_STR.lower() in ['debug'] else logging.INFO
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOG_LEVEL)

# Main function to process the rejections
def process_reject(mapped_data, ns_handler):
    for item in mapped_data:
        order_uuid = item['order_id']
        product_id = item['product_id']

        LOGGER.info(f'process_reject - order_uuid : {order_uuid}, product_id : {product_id}')

        fulfillment_uuid = get_fulfillment_id(order_uuid, product_id, ns_handler)

        if fulfillment_uuid is None:
            LOGGER.error(f'Could not find fulfillment id for item {product_id} in order {order_uuid}')
            continue

        LOGGER.info(f'Reject order {order_uuid}, product {product_id}, fulfillment_uuid {fulfillment_uuid}')

        response = False
        already_shipped_or_rejected = False

        try:
            response = ns_handler.send_item_rejection(
                reason="cannot_fulfill",
                ff_id=fulfillment_uuid,
                items_json=[product_id])
        except Exception as ex:  # pylint: disable=broad-except
            if 'already_shipped' in str(ex) or 'already_rejected' in str(ex):
                LOGGER.info('Fulfillment request has already been shipped or rejected, mark as rejected on RDS and move on.')
                already_shipped_or_rejected = True

        if not response and not already_shipped_or_rejected:
            # We remove this item of the mapped_data to not update NetSuite since it didn't work
            mapped_data.remove(item)


# Method to retrieve the rejected items data from the saved seach
def retrieve_data_from_saved_search(saved_search_id, search_page_size):
    LOGGER.info(f'savedSearchId - {saved_search_id}')

    search_type = TransactionSearchAdvanced(savedSearchScriptId=saved_search_id)

    try:
        search_preferences = SearchPreferences(
            bodyFieldsOnly=False,
            returnSearchColumns=True,
            pageSize=search_page_size
        )

        resp = client.service.search(searchRecord=search_type,
                                     _soapheaders={
                                         'searchPreferences': search_preferences,
                                         'tokenPassport': make_passport()
                                     })

        LOGGER.debug(f'Search result: {resp}')
        row_list = resp.body.searchResult.searchRowList
        if row_list is None:
            LOGGER.info('Search returned no rejected items. Nothing to process.')
            return []

        total_pages = resp.body.searchResult.totalPages
        page_size = resp.body.searchResult.pageSize
        status = resp.body.searchResult.status
        search_row = row_list.searchRow

        LOGGER.info(
            f'Results from Netsuite search - total_pages: {total_pages}, page_size: {page_size}, status: {status}'
        )
        LOGGER.debug(f'Search: {search_row}')

        mapped_data = map_netsuite_data(search_row)

        LOGGER.debug(f'retrieve_data_from_saved_search - mapped_data - {mapped_data}')
    except Exception:  # pylint: disable=broad-except
        LOGGER.error('Error during the call to the saved search.', exc_info=True)
        return []

    return mapped_data


# Data Mapping on NetSuite Data
def map_netsuite_data(data):
    transformed_item_array = []
    for item in data:
        try:
            external_id = item.basic.externalId[0].searchValue.externalId
            product_internal_id = item.basic.item[0].searchValue.internalId
            product_id = item.itemJoin.externalId[0].searchValue.externalId
            sales_order_internal_id = item.basic.internalId[0].searchValue.internalId
            sales_order_line = item.basic.line[0].searchValue
            transformed_item = {
                "order_id": external_id,
                "product_id": product_id,
                "product_internal_id": product_internal_id,
                "sales_order_internal_id": sales_order_internal_id,
                "sales_order_line": sales_order_line
            }
            transformed_item_array.append(transformed_item)
        except IndexError:
            LOGGER.info(f'Item in search does not appear to be NewStore related: {item}')
    return transformed_item_array

# Marks the items as synchronized in NewStore at Netsuite, to remove them from the Saved Search
def mark_rejected_orders_imported(mapped_data):
    """
    Extracts the sales order IDs from the mapped search results and calls for them to be updated in NetSuite
    :param mapped_data: The mapped results of the fulfillment items custom search
    """
    for result in mapped_data:
        internal_id = result['sales_order_internal_id']
        product_id = result['product_internal_id']
        line = result['sales_order_line']
        mark_rejected_order_imported(internal_id, product_id, line)


def mark_rejected_order_imported(internal_id, product_id, line):
    """
    Updates the rejected sales order synced to newstore flag on a sales order
    :param internal_id: The ID of the sales order to update
    """
    netsuite_config = Utils.get_instance().get_netsuite_config()
    rejection_flag_script_id = netsuite_config['rejection_processed_flag_script_id']

    try:
        newstore_synced_field = BooleanCustomFieldRef()
        newstore_synced_field.scriptId = rejection_flag_script_id
        newstore_synced_field.value = True

        sales_order = SalesOrder(
            internalId=internal_id,
            itemList={
                'item': [
                    {
                        'item': RecordRef(internalId=product_id),
                        'line': line,
                        'customFieldList': CustomFieldList([newstore_synced_field])
                    }
                ],
                'replaceAll': False
            }
        )

        response = client.service.update(sales_order,
                                         _soapheaders={
                                             'tokenPassport': make_passport()
                                         })
        LOGGER.debug(f'mark sales order imported - response: {response}')
        if response.body.writeResponse.status.isSuccess:
            LOGGER.info(f'Marked sales order with id "{internal_id}" as imported by NewStore in Netsuite.')
        else:
            LOGGER.error(f'Failed to mark sales order with id "{internal_id}"'
                         f' as imported by NewStore in Netsuite. Response: {response.body}')
    except Exception as e:  # pylint: disable=broad-except
        LOGGER.error(f'Error while marking the sales order with id "{internal_id}"'
                     f' as imported by NewStore in Netsuite. Error: {e}')


# Gets the ID of the fulfillment of the product
def get_fulfillment_id(order_id, product_id, ns_handler):
    distribution_centres = Utils.get_instance().get_distribution_centres()

    order_data = get_newstore_order_data(order_id, ns_handler)

    LOGGER.info(f'NewStore Order Data: {order_data}')
    if order_data is None or order_data['fulfillmentRequests'] is None:
        return None

    for fulfillment_request in order_data['fulfillmentRequests']['nodes']:
        if fulfillment_request['items'] is None:
            return None

        # the fulfillment location must be the DC to reject items for
        if fulfillment_request['fulfillmentLocationId'] not in distribution_centres.values():
            continue

        for item in fulfillment_request['items']['nodes']:
            if item['productId'] == product_id:
                return fulfillment_request['id']

    return None


# Queries the necessary NewStore order data we need for the logic using GraphQL
def get_newstore_order_data(order_id, ns_handler):
    order_data_rest = ns_handler.get_external_order(order_id, id_type='external_id')
    if order_data_rest is None:
        LOGGER.error(f'Order with ID {order_id} not found in NewStore.')
        return None

    order_uuid = order_data_rest['order_uuid']

    graphql_query = """query MyQuery($id: String!, $tenant: String!) {
  order(id: $id, tenant: $tenant) {
    id
    externalId
    fulfillmentRequests(first: 25) {
      nodes {
        items(first: 100) {
          nodes {
            id
            productId
            rejectionReason
            shippedAt
            status
          }
        }
        id
        fulfillmentLocationId
      }
    }
  }
}"""
    data = {
        "query": graphql_query,
        "variables": {
            "id": order_uuid,
            "tenant": os.environ.get('TENANT')
        }
    }

    graphql_response = ns_handler.graphql_api_call(data)
    return graphql_response['data']['order']
