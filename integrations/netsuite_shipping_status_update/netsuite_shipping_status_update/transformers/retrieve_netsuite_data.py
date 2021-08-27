import logging
import os
import time
import json
import uuid

import netsuite.netsuite_environment_loader  # pylint: disable=W0611
from netsuite.service import (
    TransactionSearchAdvanced,
    SearchPreferences,
    SearchEnumMultiSelectField,
    SearchMultiSelectField,
    SearchLongField,
    TransactionSearchBasic,
    RecordRef,
)
from netsuite.client import client as netsuite_client, make_passport
from netsuite.utils import search_records_using
from param_store.client import ParamStore
from netsuite.api.mapping import NetSuiteMapping


LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in [
    'debug'] else logging.INFO
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOG_LEVEL)

NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG = None
TENANT = os.environ['TENANT']
STAGE = os.environ['STAGE']
PARAM_STORE = ParamStore(TENANT, STAGE)


class RetrieveNetsuiteItem():
    def __init__(self, search_page_size, saved_search_id):
        self.most_recent_date_processed = None
        self.last_tran_id = None
        self.search_page_size = search_page_size
        self.saved_search_id = saved_search_id

    #
    # Netsuite call implementation to the saved search
    #
    async def get_item_fulfillment(self):
        try:
            LOGGER.info(
                f'Start get_item_fulfillment - savedSearchId - {self.saved_search_id}')

            search_preferences = SearchPreferences(
                bodyFieldsOnly=True,
                returnSearchColumns=True,
                pageSize=self.search_page_size
            )

            search_result = run_until_success(
                lambda: netsuite_client.service.search(
                    searchRecord=TransactionSearchAdvanced(
                        savedSearchScriptId=self.saved_search_id),
                    _soapheaders={
                        'searchPreferences': search_preferences,
                        'tokenPassport': make_passport()
                    }),
                function_description="Page 1 search function")

            order_tracking_data, search_results, giftcards_data = await self.main_data_mapping(search_result)

            return order_tracking_data, search_results, giftcards_data

        except Exception as e:  # pylint: disable=broad-except
            LOGGER.error(
                f"Error during the search of fulfillment item: {str(e)}", exc_info=True)

        return None

    #
    # Main function to map the data retrieved from the saved search
    #
    async def main_data_mapping(self, search_result):
        if search_result.body.searchResult.totalRecords == 0:
            LOGGER.info('There are no results to process.')
            return [], [], []

        items = search_result.body.searchResult.searchRowList.searchRow

        # LOGGER.info(f'Got items from saved search: {items}')

        data_to_update, list_internal_id = await self.map_fulfillment_data(items)

        LOGGER.info(
            f'1) Got data to update {data_to_update} and list of internal ids {list_internal_id}')

        if not data_to_update:
            return [], [], []

        mapping_internal_id_sales_order, shipping_data_list, external_id_list_newstore, product_ids_list, currency, customer_email = await self.retrieve_transaction_information(
            list_internal_id)

        LOGGER.info(
            f'Got the following info about the Sales Order: {mapping_internal_id_sales_order}; Shipping data: {shipping_data_list}')
        LOGGER.info(
            f'External ids: {external_id_list_newstore}; Product ids: {product_ids_list}')

        data_to_update = await self.add_sales_reference(data_to_update, mapping_internal_id_sales_order,
                                                        product_ids_list,
                                                        shipping_data_list)

        LOGGER.info(f'2) Got data to update {data_to_update}')

        data_to_update = await self.add_external_id_newstore(data_to_update, external_id_list_newstore)

        LOGGER.info(f'3) Got data to update {data_to_update}')

        order_tracking_data = None
        giftcards_data = None
        order_tracking_data, data_to_update, giftcards_data = await self.add_items_to_fulfill(data_to_update, currency, customer_email)

        return order_tracking_data, data_to_update, giftcards_data

    #
    # Fetch the ItemFulfillment from NetSuite and get only the fulfilled items
    # Also updates the shipping information and handles giftcards activation
    #
    async def add_items_to_fulfill(self, data_to_update, currency, customer_email):

            order_tracking_data = {}
            giftcards_data = []
            for item in data_to_update:
                try:
                    transaction_search = TransactionSearchBasic(
                        internalIdNumber=SearchLongField(
                            searchValue=int(item['itemFulfillmentInternalId']),
                            operator='equalTo'
                        ),
                        type=SearchEnumMultiSelectField(
                            searchValue=['_itemFulfillment'],
                            operator='anyOf'
                        )
                    )

                    result = run_until_success(
                        lambda: search_records_using(
                            transaction_search, self.search_page_size),
                        function_description='basic transaction search')
                    search_result = result.body.searchResult

                    if not search_result.status.isSuccess or not search_result.recordList:
                        LOGGER.error(
                            f'add_items_to_fulfill - error during the search: {search_result}')
                        return {}

                    item_fulfillment = search_result.recordList.record[0]

                    LOGGER.info(
                        f'Got ItemFulfillment from Netsuite {item_fulfillment}')

                    giftcards_data.append(
                        self.extract_giftcard_data(item_fulfillment, currency, customer_email))
                    items_fulfilled_id = [item['item']['internalId'] for item in item_fulfillment['itemList']['item'] for x in
                                        range(0, int(item['quantity']))]
                    item['itemFulfillmentItems'] = items_fulfilled_id

                    # Update shipping information
                    shipping_method_name = None
                    shipping_method_id = None
                    shipping_method = item_fulfillment['shipMethod']

                    carrier = ''
                    order_id = item['externalIdNewstore']
                    package_tracking_number = None
                    product_ids = get_product_ids_from_item_fulfillment(
                        item_fulfillment)

                    if item_fulfillment['packageList'] and item_fulfillment['packageList']['package']:
                        packages = item_fulfillment['packageList']['package']
                        for package in packages:
                            package_tracking_number = package['packageTrackingNumber']

                    if 'customFieldList' in item_fulfillment and 'customField' in item_fulfillment['customFieldList']:
                        custom_field_list = item_fulfillment['customFieldList']['customField']
                        carrier = get_carrier_from_custom_field_list(custom_field_list)

                    if shipping_method is not None:
                        shipping_method_name = shipping_method['name']
                        shipping_method_id = shipping_method['internalId']

                    tracking_numbers = None
                    if item_fulfillment['packageList'] and item_fulfillment['packageList']['package']:
                        tracking_numbers = ', '.join(list(set(
                            [item['packageTrackingNumber'] for item in item_fulfillment['packageList']['package'] if
                            item['packageTrackingNumber']])))

                    shipping_data = {
                        'shipping_method_name': shipping_method_name,
                        'shipping_method_id': shipping_method_id,
                        'trackingNumbers': tracking_numbers if tracking_numbers else item['shippingData']['linkedTrackingNumbers'],
                        'linkedTrackingNumbers': tracking_numbers if tracking_numbers else item['shippingData'][
                            'linkedTrackingNumbers']
                    }

                    item['shippingData'] = shipping_data

                    LOGGER.info(f'add_items_to_fulfill - Product Ids: {product_ids}')
                    LOGGER.info(
                        f'External ID of order -- {order_id}, Carrier = {carrier} and Tracking - {package_tracking_number}')

                    if package_tracking_number is None:
                        LOGGER.info(
                            f'add_items_to_fulfill - no package tracking number found - skip order {order_id}.')
                        continue

                    if order_id in order_tracking_data:
                        if_document_number = ''

                        if 'tranId' in item_fulfillment:
                            if_document_number = item_fulfillment['tranId']

                        location = get_location_from_item_fulfillment(item_fulfillment)

                        # Checking if the data exists already.
                        for item in order_tracking_data[order_id]:
                            # If the document_number is the same -- we append the product ids
                            # To the same IF Document number from the saved search.

                            if item['document_number'] == if_document_number:
                                item['product_ids'].extend(product_ids)
                                # Since the other details are the same except the id,
                                # We will be moving to next step.
                                continue

                        item = {
                            'product_ids': product_ids,
                            'tracking_number': package_tracking_number,
                            'carrier': carrier,
                            'order_id': order_id,
                            'location': location,
                            'document_number': if_document_number
                        }

                        order_tracking_data[order_id].append(item)

                    else:
                        if_document_number = ''
                        if 'tranId' in item_fulfillment:
                            if_document_number = item_fulfillment['tranId']

                        location = get_location_from_item_fulfillment(item_fulfillment)

                        item = {
                            'product_ids': product_ids,
                            'tracking_number': package_tracking_number,
                            'carrier': carrier,
                            'order_id': order_id,
                            'location': location,
                            'document_number': if_document_number
                        }

                        LOGGER.info(
                            f'Add Order to Order Tracking data: {order_id} ==> {item}')

                        order_tracking_data[order_id] = [item]
                except Exception as e: # pylint: disable=broad-except
                    LOGGER.info(f'Error processing item to add to fulfillment {e} ')

            return order_tracking_data, data_to_update, giftcards_data

    def extract_giftcard_data(self, item_fulfillment, currency, customer_email):
        giftcard_activation_data = []
        for items in item_fulfillment['itemList']['item']:
            result = dict(map(lambda item: (
                item['scriptId'], item['value']), items['customFieldList']['customField']))
            if 'custcol_nws_gcnumber' in result and 'custcol_fao_retailprice' in result:
                giftcard_activation_data.append(
                    {
                        'card_number': result['custcol_nws_gcnumber'],
                        'amount':
                        {
                            'value': result['custcol_fao_retailprice'],
                            'currency': currency
                        },
                        'customer':
                        {
                            'id': item_fulfillment['internalId'],
                            'email': customer_email,
                            'name': item_fulfillment['shippingAddress']['addressee'],
                            'greeting_name': item_fulfillment['shippingAddress']['addressee']
                        },
                        'metadata': {
                            'original_operation': 'activation'
                        },
                        'idempotence_key': str(uuid.uuid4())}
                )
        return giftcard_activation_data
    #
    # - Add the external id Newstore based on the createdFrom information
    #

    async def add_external_id_newstore(self, data_to_update, external_id_list_newstore):
        for data in data_to_update:
            internal_id = data['createdFrom']
            external_id = external_id_list_newstore.get(internal_id)
            data['externalIdNewstore'] = external_id
        return data_to_update

    #
    # Add the sales reference to the data
    # mapping_internal_id_sales_order contains the internalId and return the sales order reference
    #
    async def add_sales_reference(self,
                                  data_to_update,
                                  mapping_internal_id_sales_order,
                                  product_ids_list,
                                  shipping_data_list):
        for item in data_to_update:
            internal_id = item.get('createdFrom')
            sales_order = mapping_internal_id_sales_order.get(internal_id)
            item_list = product_ids_list.get(internal_id)
            shipping_data = shipping_data_list.get(internal_id)

            item['salesOrder'] = sales_order
            item['salesOrderItems'] = item_list
            item['shippingData'] = shipping_data
        return data_to_update

    #
    # Map the itenFulfillment data from Netsuite
    #
    async def map_fulfillment_data(self, items):
        list_internal_id = []
        output = []

        for item in items:
            # LOGGER.info(f'Process Item: {item}')

            tran_date = item.basic.tranDate[0].searchValue.isoformat()
            created_from_internal_id = item.basic.createdFrom[0].searchValue.internalId
            item_fulfillment_internal_id = item.basic.internalId[0].searchValue.internalId
            tran_id = item.basic.tranId[0].searchValue
            items = item.basic.item

            output.append({"tranDate": tran_date,
                           "status": "shipped",
                           "createdFrom": created_from_internal_id,
                           "tranId": tran_id,
                           "salesOrder": None,
                           "itemFulfillmentInternalId": item_fulfillment_internal_id,
                           "items": items})
            list_internal_id.append(int(created_from_internal_id))
        return output, list_internal_id

    #
    # Retrieve Netsuite additional information from the internal id about this Sales Order
    # to be able to add the SalesOrder reference in the SQS message
    # in addition the method will return a mapping between item internalId and item Name
    # Retrieve the shipping Method
    # - Return the mapping information between Internal id and Newstore external id
    #
    async def retrieve_transaction_information(self, list_internal_id):
        try:
            transaction_type = '_salesOrder'
            id_references = [RecordRef(internalId=id)
                             for id in list_internal_id]
            transaction_search = TransactionSearchBasic(
                type=SearchEnumMultiSelectField(
                    searchValue=[transaction_type],
                    operator='anyOf'

                ),
                internalId=SearchMultiSelectField(
                    searchValue=id_references,
                    operator='anyOf'
                )
            )

            result = run_until_success(
                lambda: search_records_using(
                    transaction_search, self.search_page_size),
                function_description='retrieval of transaction information')
            r = result.body.searchResult

            mapping_internal_id_sales_order = {}
            shipping_data_list = {}
            external_id_list_newstore = {}
            product_ids_list = {}

            if not r.status.isSuccess or not r.recordList:
                LOGGER.error(
                    f'retrieve_transaction_information - error during the search: {r}')
                return {}
            LOGGER.info(
                f'Sales Transaction retrieved: {r.recordList}')

            for record_item in r.recordList.record:
                shipping_method_name = None
                shipping_method_id = None

                external_id_newstore = record_item['externalId']
                internal_id_value = record_item['internalId']
                tran_id = record_item['tranId']
                mapping_internal_id_sales_order[internal_id_value] = tran_id
                item_list = record_item['itemList']['item']
                currency = NetSuiteMapping().get_currency_code(
                    record_item['currency']['internalId'])
                customer_email = record_item['email']
                shipping_method = record_item['shipMethod']
                if shipping_method is not None:
                    shipping_method_name = shipping_method['name']
                    shipping_method_id = shipping_method['internalId']
                tracking_numbers = record_item['trackingNumbers']
                linked_tracking_numbers = record_item['linkedTrackingNumbers']

                shipping_data = {
                    "shipping_method_name": shipping_method_name,
                    "shipping_method_id": shipping_method_id,
                    "trackingNumbers": tracking_numbers,
                    "linkedTrackingNumbers": linked_tracking_numbers
                }
                shipping_data_list[internal_id_value] = shipping_data
                product_id_list = [item['item']['internalId']
                                   for item in item_list]
                product_ids_list[internal_id_value] = product_id_list
                external_id_list_newstore[internal_id_value] = external_id_newstore

            return mapping_internal_id_sales_order, shipping_data_list, external_id_list_newstore, product_ids_list, currency, customer_email

        except Exception as e:  # pylint: disable=broad-except
            LOGGER.error(
                f'retrieve_transaction_information - error: {e}', exc_info=True)
            return None


def run_until_success(function_to_run, function_description='method', max_tries=10, seconds_between_runs=10):
    result = None
    success = False
    last_exception = None
    for attempt in range(0, max_tries):
        try:
            result = function_to_run()
            success = True
            break
        except Exception as e:  # pylint: disable=broad-except
            LOGGER.warning(
                f'Failed running {function_description}. Error: {str(e)}', exc_info=True)
            last_exception = e
            time.sleep(seconds_between_runs)

    if success:
        return result
    else:
        raise ValueError(
            f'Made {max_tries} attempts to run {function_description} but failed with this error: {str(last_exception)}')


def get_product_ids_from_item_fulfillment(item_fulfillment):
    newstore_to_netsuite = json.loads(PARAM_STORE.get_param('newstore/newstore_to_netsuite_product_mapping'))

    LOGGER.info(f"Before mapping item_fulfillments ${item_fulfillment}")

    items = item_fulfillment['itemList']['item']
    ids = []

    for item in items:
        item_name = str(item['itemName'])
        if item_name in newstore_to_netsuite:
            ids.append(newstore_to_netsuite[item_name])
            continue
        ids.append(item_name)

    LOGGER.info(f"After mapping item_fulfillments ${ids}")
    return ids

#
# Gets the carrier name from a custom field. F&O uses a module called
# ShipHawk in the warehouse, and they set the below custom field as carrier.
#


def get_carrier_from_custom_field_list(custom_field_list):
    for custom_field in custom_field_list:
        script_id = custom_field['scriptId']
        if script_id == 'custbody_shiphawk_carrier_name':
            return str(custom_field['value'])

    return False


def get_location_from_item_fulfillment(item_fulfillment):
    items = item_fulfillment['itemList']['item']
    location = ''

    for item in items:
        if 'location' in item:
            location_id = item['location']['internalId']
            location = get_newstore_location_from_netsuite_internal_id(
                location_id)

    return location


def get_newstore_location_from_netsuite_internal_id(location_internal_id):
    newstore_to_netsuite_locations = get_newstore_to_netsuite_locations_config()
    for newstore_location_id in newstore_to_netsuite_locations:
        location_config = newstore_to_netsuite_locations[newstore_location_id]
        if str(location_config['id']) == str(location_internal_id):
            return newstore_location_id

    return ''


def get_newstore_to_netsuite_locations_config():
    global NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG  # pylint: disable=W0603
    if not NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG:
        NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG = json.loads(
            PARAM_STORE.get_param('netsuite/newstore_to_netsuite_locations'))
    return NEWSTORE_TO_NETSUITE_LOCATIONS_CONFIG
