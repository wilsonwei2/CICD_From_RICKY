import os
import json
import logging
from lambda_utils.sqs.SqsHandler import SqsHandler
# from product_id_mapper.main import ProductIdMapper
from .utils import get_shopify_handler, get_newstore_handler


# PRODUCT_ID_MAPPER = ProductIdMapper()

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

SQS_HANDLER = SqsHandler(os.environ['sqs_returns_name'])

SHOPIFY_HANDLER = None


def handler(event, context): # pylint: disable=unused-argument
    """
    Start of the lambda handler
    :param event: Shopify webhook order json
    :param context: function context
    """
    LOGGER.info(f'Processing return Event: {event}')
    newstore_handler = get_newstore_handler(context)

    for record in event.get('Records', []):
        try:
            response_bool = _process_refund(record['body'], newstore_handler)
            if response_bool:
                LOGGER.info('Event processed, deleting message from queue...')
                SQS_HANDLER.delete_message(record['receiptHandle'])
            else:
                LOGGER.error(f'Failed to process event: {record["body"]}')
        except Exception as ex: # pylint: disable=broad-except
            LOGGER.exception('Some error happen while processing the return')
            # In case an other process already returned the product we delete it from the queue to avoid exeptions again and again.
            err_msg = str(ex)
            if err_msg.find("The following products were already returned") >= 0:
                LOGGER.info('If the product was already returnd we delete the message from queue:')
                SQS_HANDLER.delete_message(record['receiptHandle'])

            continue


def _process_refund(raw, newstore_handler):
    LOGGER.info(f'Processing Shopify refund event: {raw}')
    refund = json.loads(raw)
    # Transform Shopify format to NS format
    data_to_send = _transform_data_to_send(refund)
    shop_id = refund['shop_id']
    if len(refund.get('refund_line_items', [])) == 0:
        LOGGER.info('Processing an order appeasment')
        return _create_refund(data_to_send, refund, newstore_handler, shop_id)
    LOGGER.info('Processing an order return')
    return _create_return(data_to_send, refund, newstore_handler, shop_id)


def _create_refund(refund_data, refund, newstore_handler, shop_id):
    LOGGER.info(f'Data for refund {json.dumps(refund_data, indent=4)}')
    ns_external_order_id = get_order_name(refund['order_id'], shop_id)
    ns_order = _get_external_order(ns_external_order_id, newstore_handler)

    if ns_order:
        ns_order_id = ns_order['order_uuid']
        if not _refund_exists(newstore_handler.get_refunds(ns_order_id), refund['id']) and \
            not _refund_started_in_newstore(refund.get('note') or ''):
            # Send return to NewStore
            request_refund = {
                'amount': refund_data['amount'],
                'currency': refund_data['currency'],
                'extended_attributes': _map_refund_id_ext_attr(refund),
                'note': refund_data.get('reason') or '',
                'is_historical': True,
            }
            response = newstore_handler.create_refund(ns_order_id, request_refund)
            LOGGER.info(f'Refund created: {json.dumps(response)}')
            return True
        LOGGER.info(f'Refund already exists on NewStore for order {ns_order_id}')
        return True
    return False


def _create_return(return_data, refund, newstore_handler, shop_id):
    LOGGER.info(f'Data for return {json.dumps(return_data, indent=4)}')
    ns_external_order_id = get_order_name(refund['order_id'], shop_id)
    ns_order = _get_external_order(ns_external_order_id, newstore_handler)

    if ns_order:
        ns_order_id = ns_order['order_uuid']
        if not _refund_exists(newstore_handler.get_refunds(ns_order_id).get('refunds'), refund['id']) and \
            not _refund_started_in_newstore(refund.get('note') or ''):
            # Send return to NewStore
            request_return = {
                'items': return_data['items'],
                'returned_from': os.environ['warehouse_usc'],
                'returned_at': return_data['processed_at'],
                'extended_attributes': _map_refund_id_ext_attr(refund)
            }
            if return_data.get('amount'):
                request_return['refund_amount'] = return_data['amount']
            response = newstore_handler.create_return(ns_order_id, request_return)
            LOGGER.info(f'Return created: {json.dumps(response)}')
            return True
        LOGGER.info(f'Return already exists on NewStore for order {ns_order_id}')
        return True
    return False


def _get_external_order(external_order_id, newstore_handler):
    try:
        return newstore_handler.get_external_order(external_order_id.replace("#", ""))
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


def _get_shopify_return_id_from_ext_attr(extended_attributes): # pylint: disable=invalid-name
    # The refund id on Shopify is an integer
    return int(next((attr.get('value') for attr in extended_attributes if attr.get('name') == 'shopify_refund_id'), 0))


def _refund_started_in_newstore(note: str) -> bool:
    return note.startswith('Newstore originated refund')


def _map_refund_id_ext_attr(refund):
    refund_transactions_ids = ','.join(str(transaction.get('id')) for transaction in refund.get(
        'transactions', []) if transaction.get('status') == 'success')
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
        LOGGER.error(
            f'No currency could be detected.\n\nTransactions: {json.dumps(transactions)}')
        raise Exception('We could not detect the currency type;')
    LOGGER.error(
        f'Multiple currencies detected on the refund requests.\nCurrencies: {currencies}\nTransactions: {json.dumps(transactions)}')
    raise Exception(
        'Newstore do not support multiple currencies for refunds')


def _transform_data_to_send(refund_webhook):
    ####
    # Transforms the data received on the webhook to match what NewStore receives on return endpoint
    # Returns the data ready to be send to NewStore
    ####
    product_ids = []
    reason = refund_webhook.get('note') or ''
    refund_value = _get_successful_refunds_value(
        refund_webhook.get('transactions', []))
    for item in refund_webhook['refund_line_items']:
        if item.get('line_item', {}).get('fulfillment_status') == 'fulfilled':
            for _ in range(item['quantity']):
                product_ids.append(
                    {
                        'product_id': item['line_item']['sku'],
                        'return_reason': reason
                    }
                )
    return {
        'items': product_ids,
        'amount': refund_value,
        'reason': reason,
        'processed_at': refund_webhook['processed_at'],
        'currency': _get_refund_currency(refund_webhook.get('transactions', []))
    }
