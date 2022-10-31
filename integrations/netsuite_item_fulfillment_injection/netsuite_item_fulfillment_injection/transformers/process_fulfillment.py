import logging
from netsuite.service import (
    RecordRef,
    ItemFulfillmentPackage,
    ItemFulfillmentPackageList
)
from netsuite_item_fulfillment_injection.helpers.utils import Utils

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)


def parse_info(fulfillment_request, sales_order, item_fulfillment):
    LOGGER.info('Parsing info')
    # Map item fulfillment items
    LOGGER.info('Map ItemFulfillmentItems')
    item_fulfillment_items = map_item_fulfillment_items(fulfillment_request)
    # Map item fulfillment packages
    LOGGER.info('Map ItemFulfillmentPackages')
    item_fulfillment_packages = map_item_fulfillment_packages(fulfillment_request)
    # Map item fulfillment
    LOGGER.info('Map ItemFulfillment')
    item_fulfillment = map_item_fulfillment(fulfillment_request, sales_order, item_fulfillment_packages, item_fulfillment)

    return item_fulfillment, item_fulfillment_items


def map_item_fulfillment(fulfillment_request, sales_order, item_fulfillment_packages, item_fulfillment):
    if 'createdDate' in item_fulfillment:
        del item_fulfillment['createdDate']
    item_fulfillment['externalId'] = fulfillment_request['id']
    item_fulfillment['createdFrom'] = RecordRef(internalId=sales_order.internalId)
    item_fulfillment['customForm'] = RecordRef(internalId=int(Utils.get_netsuite_config()['item_fulfillment_custom_form_internal_id']))
    item_fulfillment['packageList'] = ItemFulfillmentPackageList(item_fulfillment_packages)
    item_fulfillment['shipStatus'] = '_shipped'
    return item_fulfillment


def map_item_fulfillment_items(fulfillment_request):
    item_fulfillment_items = []
    netsuite_location = Utils.get_netsuite_store_internal_id(fulfillment_request['fulfillmentLocationId'])
    grouped_products = group_products_by_id(fulfillment_request.get('items'))

    for product_id in grouped_products:
        item_fulfillment_item = {
            'item': RecordRef(internalId=product_id),
            'location': RecordRef(internalId=netsuite_location),
            'quantity': grouped_products[product_id],
            'itemReceive': True
        }
        item_fulfillment_items.append(item_fulfillment_item)

    return item_fulfillment_items


def group_products_by_id(product_list):
    grouped_products = {}
    for product in product_list['edges']:
        product_id = product['node']['productId']
        if product_id in grouped_products:
            grouped_products[product_id] += 1
        else:
            grouped_products[product_id] = 1
    return grouped_products


def map_item_fulfillment_packages(fulfillment_request):
    item_fulfillment_packages = []
    shipment_list = {}
    for product in fulfillment_request['items']['edges']:
        tracking_code = product['node'].get('trackingCode', 'N/A')
        if tracking_code not in shipment_list:
            shipment_list[tracking_code] = [product['node']['productId']]
        else:
            shipment_list[tracking_code].append(product['node']['productId'])

    for shipment_tracking_code in shipment_list:
        item = {
            'packageDescr': '; '.join(shipment_list[shipment_tracking_code]),
            'packageTrackingNumber': shipment_tracking_code,
            'packageWeight': 1
        }
        item_fulfillment_packages.append(ItemFulfillmentPackage(**item))
    return item_fulfillment_packages


def _get_non_null_field(array, field, default_value):
    value = array.get(field)
    return default_value if value is None else value
