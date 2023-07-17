import os
import json
import logging
from lambda_utils.sqs.SqsHandler import SqsHandler
# from product_id_mapper.main import ProductIdMapper
from .utils import get_shopify_handler, get_newstore_handler, get_shopify_locations_map


# PRODUCT_ID_MAPPER = ProductIdMapper()

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

SQS_HANDLER = SqsHandler(os.environ['sqs_returns_name'])

SHOPIFY_HANDLER = None
NEWSTORE_HANDLER = None


def handler(event, context):  # pylint: disable=unused-argument
    """
    Start of the lambda handler
    :param event: Shopify webhook order json
    :param context: function context
    """
    LOGGER.info(f'Processing return Event: {event}')

    global NEWSTORE_HANDLER  # pylint: disable=W0603
    NEWSTORE_HANDLER = get_newstore_handler(context)

    for record in event.get('Records', []):
        try:
            response_bool = _process_refund(record['body'])
            if response_bool:
                LOGGER.info('Event processed, deleting message from queue...')
                SQS_HANDLER.delete_message(record['receiptHandle'])
            else:
                LOGGER.error(f'Failed to process event: {record["body"]}')
        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.exception('Some error happen while processing the return')
            # In case an other process already returned the product we delete it from the queue to avoid exeptions again and again.
            err_msg = str(ex)
            if err_msg.find("The following products were already returned") >= 0:
                LOGGER.info(
                    'If the product was already returnd we delete the message from queue:')
                SQS_HANDLER.delete_message(record['receiptHandle'])

            continue


def _process_refund(raw):
    LOGGER.info(f'Processing Shopify refund event: {raw}')
    refund = json.loads(raw)
    shop_id = refund['shop_id']
    #get updated transactions from shopify
    shopify_handler = get_shopify_handler(shop_id)
    shopify_refunds = shopify_handler.get_order(refund.get('order_id'), params='refunds')
    LOGGER.info(f'shopify refunds {shopify_refunds}')
    # transactions = shopify_refunds.get('refunds', [])[-1].get('transactions', [])
    transactions = refund.get('transactions', [])
    LOGGER.info(f'Latest transactions from Shopify for {refund.get("order_id")}: {transactions}')
    # Transform Shopify format to NS format
    data_to_send = _transform_data_to_send(refund, transactions)
    # if the reurn is pending, send False to handler so message will be requeued
    if data_to_send['currency'] == "pending":
        LOGGER.info(f'Return is pending. Will not processed until status = success. Sending back to SQS')
        SQS_HANDLER.push_message(message=json.dumps(refund))
        return False
    if len(refund.get('refund_line_items', [])) == 0:
        LOGGER.info('Processing an order appeasment')
        return _create_refund(data_to_send, refund, shop_id, transactions)
    LOGGER.info('Processing an order return')
    return _create_return(data_to_send, refund, shop_id, transactions)


def _create_refund(refund_data, refund, shop_id, transactions):
    LOGGER.info(f'Data for refund {json.dumps(refund_data, indent=4)}')
    ns_external_order_id = get_order_name(refund['order_id'], shop_id)
    ns_order = _get_external_order(ns_external_order_id)

    if ns_order:
        ns_order_id = ns_order['order_uuid']
        is_refund_exists = _refund_exists(
            NEWSTORE_HANDLER.get_refunds(ns_order_id), refund['id'])
        LOGGER.info(f'Get Refunds {is_refund_exists}')
        is_refund_start_in_newstore = _refund_started_in_newstore(
            refund.get('note') or '')
        LOGGER.info(
            f'Refund started in NewStore {is_refund_start_in_newstore}')

        if not is_refund_exists and not is_refund_start_in_newstore:
            # Send return to NewStore
            request_refund = {
                'amount': refund_data['amount'],
                'currency': refund_data['currency'],
                'extended_attributes': _map_refund_id_ext_attr(refund, transactions),
                'note': refund_data.get('reason') or '',
                'is_historical': True,
            }
            response = NEWSTORE_HANDLER.create_refund(
                ns_order_id, request_refund)
            LOGGER.info(f'Refund created: {json.dumps(response)}')
            return True
        LOGGER.info(
            f'Refund already exists on NewStore for order {ns_order_id}')
        return True
    return False


def _create_return(return_data, refund, shop_id, transactions):
    LOGGER.info(f'Data for return {json.dumps(return_data, indent=4)}')
    ns_external_order_id = get_order_name(refund['order_id'], shop_id)
    ns_order = _get_external_order(ns_external_order_id)

    if ns_order:
        ns_order_id = ns_order['order_uuid']
        is_refund_exists = _refund_exists(
            NEWSTORE_HANDLER.get_refunds(ns_order_id), refund['id'])
        LOGGER.info(f'Get Refunds {is_refund_exists}')
        is_refund_start_in_newstore = _refund_started_in_newstore(
            refund.get('note') or '')
        LOGGER.info(
            f'Refund started in NewStore {is_refund_start_in_newstore}')
        if not is_refund_exists and not is_refund_start_in_newstore:
            # Send return to NewStore
            returned_from = get_returned_from(refund)
            request_return = {
                'items': return_data['items'],
                'returned_from': returned_from,
                'returned_at': return_data['processed_at'],
                'extended_attributes': _map_refund_id_ext_attr(refund, transactions)
            }
            if return_data.get('amount'):
                request_return['refund_amount'] = return_data['amount']
            response = NEWSTORE_HANDLER.create_return(
                ns_order_id, request_return)
            LOGGER.info(f'Return created: {json.dumps(response)}')
            return True
        LOGGER.info(
            f'Return already exists on NewStore for order {ns_order_id}')
        return True
    return False


def _get_external_order(external_order_id):
    try:
        return NEWSTORE_HANDLER.get_external_order(external_order_id.replace("#", ""))
    except Exception as ex: # pylint: disable=broad-except
        LOGGER.error('Couldn\'t get order from NewStore.')
        LOGGER.exception(str(ex))
    return None


def get_order_name(order_id, shop_id):
    shopify_handler = get_shopify_handler(shop_id)
    order = shopify_handler.get_order(order_id, params='name')
    if not order:
        LOGGER.error('Couldn\'t get order from Shopify.')
        return None
    order_name = order.get('name')
    if not order_name:
        LOGGER.error('Order name is null.')
        return None
    return order_name


def _refund_exists(ns_refunds, shopify_return_id):
    if ns_refunds:
        LOGGER.info(f'Validating refund exists for {json.dumps(ns_refunds)}')
        for ns_refund in ns_refunds:
            ns_shopify_return_id = _get_shopify_return_id_from_ext_attr(
                ns_refund.get('metadata', {}).get('extended_attributes', []))
            if ns_shopify_return_id == shopify_return_id:
                return True
    return False


def _get_shopify_return_id_from_ext_attr(extended_attributes):  # pylint: disable=invalid-name
    # The refund id on Shopify is an integer
    return int(next((attr.get('value') for attr in extended_attributes if attr.get('name') == 'shopify_refund_id'), 0))


def _refund_started_in_newstore(note: str) -> bool:
    return note.startswith('Newstore originated refund')


def _map_refund_id_ext_attr(refund, transactions):
    refund_transactions_ids = ','.join(str(transaction.get('id')) for transaction in transactions
                                       if transaction.get('status') == 'success')
    return [
        {
            'name': 'shopify_refund_id',
            'value': str(refund['id'])
        },
        {
            'name': 'shopify_refund_transactions_ids',
            'value': str(refund_transactions_ids)

        }
    ]


def _get_successful_refunds_value(transactions):
    return sum(
        (float(transaction['amount'])
         for transaction in transactions
         if transaction.get('kind') in ['void', 'refund']
         and transaction.get('status') == 'success'), 0)


def _get_refund_currency(transactions):
    currencies = [transaction['currency'].upper() for transaction in transactions if transaction.get(
        'kind') in ['void', 'refund'] and transaction.get('status') == 'success']
    currency = list(dict.fromkeys(currencies))
    if len(currency) == 1:
        return str(currency[0])
    if len(currency) == 0:
        if "pending" in [transaction.get('status') for transaction in transactions]:
            LOGGER.info('order status is pending')
            return "pending"
        LOGGER.error(
            f'No currency could be detected.\n\nTransactions: {json.dumps(transactions)}')
        raise Exception('We could not detect the currency type;')
    LOGGER.error(
        f'Multiple currencies detected on the refund requests.\nCurrencies: {currencies}\nTransactions: {json.dumps(transactions)}')
    raise Exception(
        'Newstore do not support multiple currencies for refunds')


def _transform_data_to_send(refund_webhook, transactions):
    ####
    # Transforms the data received on the webhook to match what NewStore receives on return endpoint
    # Returns the data ready to be send to NewStore
    ####
    product_ids = []
    reason = refund_webhook.get('note') or ''
    refund_value = _get_successful_refunds_value(transactions)
    LOGGER.debug(f'refund value: {refund_value}')
    for item in refund_webhook['refund_line_items']:
        product_id = item['line_item']['sku']

        if item.get('line_item', {}).get('fulfillment_status') == 'fulfilled':
            for _ in range(item['quantity']):
                product_ids.append(
                    {
                        'product_id': item['line_item']['sku'],
                        'return_reason': reason
                    }
                )
        else:
            LOGGER.info(
                f'Product {product_id} not fulfilled - will not be added to the refund item list')
    return {
        'items': product_ids,
        'amount': refund_value,
        'reason': reason,
        'processed_at': refund_webhook['processed_at'],
        'currency': _get_refund_currency(transactions)
    }


def get_returned_from(refund):
    shopify_location_id = int(refund['refund_line_items'][0]['location_id'])
    locations_map = {int(loc_id): key for key, value in get_shopify_locations_map().items() for loc_id in value.values()}
    return locations_map.get(shopify_location_id, os.environ['warehouse_usc'])
