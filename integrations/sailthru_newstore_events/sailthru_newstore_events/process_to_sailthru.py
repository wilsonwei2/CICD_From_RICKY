import os
import logging
import json
from lambda_utils.sqs.SqsHandler import SqsHandler
from .handlers.lambda_handler import start_lambda_function
from .utils import get_param
from newstore_common.aws import init_root_logger
from newstore_adapter.connector import NewStoreConnector

init_root_logger(__name__)
LOGGER = logging.getLogger(__name__)

TENANT = os.environ.get('TENANT')

def handler(event, context): # pylint: disable=unused-argument
    result = _read_from_queue(event, context)
    return result


def _read_from_queue(event: dict, context):
    sqs_handler = SqsHandler(os.environ['SAILTHRU_QUEUE'])
    for record in event.get('Records', []):
        try:
            event = json.loads(record['body'])
            LOGGER.info(f'Processing Event: {json.dumps(event)}')
            response = _process_event(event["payload"], event['name'], context)
            LOGGER.info(f'Response: {response}')
            LOGGER.info('Deleting message from queue...')
            sqs_handler.delete_message(record['receiptHandle'])
        except Exception as e:
            raise e
    return 'Messages processed'


def _process_event(data: dict, event_name: str, context):
    """
    Args:
        data (dict): customer.created event payload
    """
    ns_handler = NewStoreConnector(
        tenant=TENANT,
        context=context
    )
    ns_order = ns_handler.get_external_order(data.get('order_id', data['id']), id_type='id')
    to_process_countries = os.environ.get('TO_PROCESS_COUNTRIES')
    if to_process_countries and _get_country_code(ns_order) not in to_process_countries:
        return f'Order {data["order_id"]} not in list of countries to process, ignoring...'
    LOGGER.info(f'NewStore order: {json.dumps(ns_order)}')
    if 'fulfillment' in event_name:
        body = _sailthru_mapping_sc(data, ns_order)
    else:
        body = _sailthru_mapping_oc(data, ns_order)
    if not body:
        return {}
    payload = {
        'body': json.dumps(body)
    }
    return start_lambda_function(
                os.environ.get('INVOKE_SAILTHRU_LAMBDA', f'{TENANT}-sailthru'),
                payload=payload)


# shipping confirmation data mapping
def _sailthru_mapping_sc(data, order):
    country = order['shipping_address']['country_code']
    templates = get_param(os.environ.get('SAILTHRU_TEMPLATES_PARAM', 'sailthru_templates'))
    # get language of template with store id as mapped in parameter, default to english
    template_language = get_param(
        os.environ.get('STORE_LANGUAGE_MAPPING', 'non_english_store_language_mapping')).get(
            data['fulfillment_location_id'], 'english')
    # lots of different countries utilize EU templates, use as default if no mapping found for specific country
    template = templates.get(
        f'template_{country.lower()}', templates['template_ca'])[template_language].get('ship_confirmation')
    if not template:
        LOGGER.info(
            f'No template exists for this shipping confirmation event. '
            f'Country code: {country}, language: {template_language}.'
        )
        return {}
    shipped_products = _get_payload_items_details(order['ordered_products'], data['items'])
    shipment = _get_apropos_shipment(
        order['shipments'], next((item['tracking_code'] for item in data['items'] if item.get('tracking_code')), None))
    assert shipment, 'No shipment could be found for tracking code from event.'
    try:
        payload = {
            'template': template,
            'email': order['billing_address'].get('email'),
            'vars': {
                'items': [
                    {
                        'material': product['name'],
                        'materialNumber': product['id'],
                        'gridText': '',
                        'quantity': product['quantity'],
                        'price': f'{product["price"]["gross"]} {product["price"]["currency"]}',
                        'season': _get_extended_attribute(product['extended_attributes'], 'season_code', ''),
                        'image': product['image'],
                        'images': {
                            'full': {
                                'url': product['image']
                            }
                        }
                    } for product in shipped_products.values()
                ],
                'ORDERPLACEDDATE': order['created_at'],
                'ORDERNUMBER': order['external_order_id'],
                'TRACKINGURL': next((
                    package['tracking_url'] for package in shipment.get('details', {}).get('shipping_packages', [])
                    if package.get('tracking_url')), ''),
                'SHIPPINGNAME':
                    f'{order["shipping_address"].get("first_name", "")} {order["shipping_address"].get("last_name", "")}',
                'SHIPPINGADDRESS2': order['shipping_address'].get('address_line_1', ''),
                'SHIPPINGCITY': order['shipping_address'].get('city', ''),
                'SHIPPINGSTATE': order['shipping_address'].get('state', ''),
                'SHIPPINGPOSTAL': order['shipping_address'].get('zip_code', ''),
                'SHIPPINGCOUNTRY': order['shipping_address'].get('country_code', ''),
                'BILLINGNAME':
                    f'{order["billing_address"].get("first_name", "")} {order["billing_address"].get("last_name", "")}',
                'BILLINGADDRESS1': order['billing_address'].get('address_line_1', ''),
                'BILLINGADDRESS2': order['billing_address'].get('address_line_2', ''),
                'BILLINGCITY': order['billing_address'].get('city', ''),
                'BILLINGSTATE': order['billing_address'].get('state', ''),
                'BILLINGPOSTAL': order['billing_address'].get('zip_code', ''),
                'BILLINGCOUNTRY': order['billing_address'].get('country_code', ''),
                'SUBTOTAL': f'{order["totals"]["order_total"]} {order["totals"]["currency"]}',
                'COD': '0.00',
                'ORDERDISCOUNT': '0.00 USD',
                'SHIPPING':
                    f'{order["totals"]["shipping_total"]+order["totals"]["shipping_taxes"]} {order["totals"]["currency"]}',
                'SALESTAX': f'{order["totals"]["taxes"]} {order["totals"]["currency"]}',
                'SHIPPINGMETHOD': shipment.get('details', {}).get('method', ''),
                'TOTAL': f'{order["totals"]["grand_total"]} {order["totals"]["currency"]}',
                'PREFECTURE': '',
                'DELIVERYINSTRUCTIONS': '',
                'PAYMETHOD': '',
                'REQUESTSHIPDATE': '',
                'REQUESTSHIPTIME': ''
            }
        }
    except Exception as e:
        LOGGER.info('Error transforming payload.')
        raise e
    LOGGER.info(f'Created payload: {json.dumps(payload)}')
    return payload


# order cancellation data mapping
def _sailthru_mapping_oc(data, order):
    country = order['shipping_address']['country_code']
    templates = get_param(os.environ.get('SAILTHRU_TEMPLATES_PARAM', 'sailthru_templates'))
    # get language of template with store id as mapped in parameter, default to english
    template_language = get_param(
        os.environ.get('STORE_LANGUAGE_MAPPING', 'non_english_store_language_mapping')).get(
            order['channel'], 'english')
    # burton_cancel_codes = os.environ['BURTON_CANCEL_CODES'].split(',')
    # cancellation_type = 'burton_cancel' \
    #    if str(data['items'][0]['cancellation_code']) in burton_cancel_codes else 'customer_cancel'
    # lots of different countries utilize EU templates, use as default if no mapping found for specific country
    template = templates.get(
        f'template_{country.lower()}', templates['template_ca'])[template_language].get('order_cancel')
    #    f'template_{country.lower()}', templates['template_eu'])[template_language].get(cancellation_type)
    if not template:
        LOGGER.info(
            f'No template exists for this order cancellation event. '
            f'Country code: {country}, language: {template_language}.'
        )
        return {}
    cancelled_products = _get_payload_items_details(order['ordered_products'], data['items'])
    payload = {
        'template': template,
        'email': order['billing_address'].get('email'),
        'vars': {
            'items': [
                {
                    'material': product['name'],
                    'materialNumber': product['id'],
                    'gridText': '',
                    'quantity': product['quantity'],
                    'price': f'{product["price"]["gross"]} {product["price"]["currency"]}',
                    'season': _get_extended_attribute(product['extended_attributes'], 'season_code', ''),
                    'image': product['image'],
                    'images': {
                        'full': {
                            'url': product['image']
                        }
                    }
                } for product in cancelled_products.values()
            ],
            'BILLINGNAME':
                f'{order["billing_address"].get("first_name", "")} {order["billing_address"].get("last_name", "")}',
            'ORDERNUMBER': order['external_order_id']
        }
    }
    LOGGER.info(f'Created payload: {json.dumps(payload)}')
    return payload


def _get_extended_attribute(extended_attributes: dict, attribute_name: str, default: str = None):
    for attr in extended_attributes:
        if attr['name'] == attribute_name:
            return attr['value']
    return default


def _get_country_code(ns_order):
    return ns_order['shipping_address'].get('country_code', ns_order['billing_address'].get('country_code', ''))


def _get_payload_items_details(ordered_products, payload_items):
    details = {}
    for item in payload_items:
        if details.get(item['product_id']):
            details[item['product_id']]['quantity'] += 1
        else:
            details[item['product_id']] = next(
                product for product in ordered_products if product['id'] == item['product_id'])
            details[item['product_id']]['quantity'] = 1
    return details


def _get_apropos_shipment(shipments, tracking_code):
    if tracking_code is None:
        LOGGER.exception('Missing tracking code, cannot map to correct shipment.')
        return {}
    for shipment in shipments:
        if shipment.get('details', {}).get('shipping_packages', []) and next((
                True for package in shipment['details']['shipping_packages']
                if package.get('tracking_code') == tracking_code), False):
            return shipment
    return {}
