import logging
from netsuite_transfer_updates_to_netsuite.helpers.exceptions import StoreMappingException
from netsuite_transfer_updates_to_netsuite.helpers.utils import Utils
from netsuite.service import (
    RecordRef
)

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)


async def create_item_receipt(item_fulfillment, items_received_event, store):
    fulfillment_location_id = items_received_event['fulfillment_location_id']
    netsuite_location_id = Utils.get_netsuite_store_internal_id(fulfillment_location_id)

    if not netsuite_location_id:
        raise StoreMappingException(f"fulfillment_location_id, {fulfillment_location_id}, isn't mapped to NetSuite")

    received_items, overage_items = await map_received_items(received_items=items_received_event.get('items', []),
                                                             receiving_store_location_id=netsuite_location_id,
                                                             item_fulfillment_items=item_fulfillment['itemList']['item'])

    store_country_code = Utils.get_one_of_these_fields(params=store['physical_address'],
                                                       fields=['country', 'country_code'])

    currency_id = Utils.get_currency_from_country_code(country_code=store_country_code)
    subsidiary_id = Utils.get_subsidiary_from_currency(currency_id)

    tran_date = Utils.format_datestring_for_netsuite(date_string=items_received_event['processed_at'],
                                                     time_zone=store['timezone'])

    # The item fulfillment and item receipts must be parented by the same Transfer Order
    transfer_order_internal_id = item_fulfillment['createdFrom']['internalId']
    item_receipt = {
        'customForm': RecordRef(internalId=int(Utils.get_netsuite_config()['item_receipt_custom_form'])),
        'subsidiary': RecordRef(internalId=subsidiary_id),
        'createdFrom': RecordRef(internalId=transfer_order_internal_id),
        'itemFulfillment': RecordRef(internalId=item_fulfillment['internalId']),
        'currency': RecordRef(internalId=currency_id),
        'tranDate': tran_date.date(),
        'itemList': {
            "item": received_items,
            "replaceAll": False
        }
    }

    inventory_adjustment = None
    if overage_items:
        inventory_adjustment = {
            'customForm': RecordRef(internalId=int(Utils.get_netsuite_config()['inventory_adjustment_custom_form'])),
            'subsidiary': RecordRef(internalId=subsidiary_id),
            'tranDate': tran_date.isoformat(),
            'adjLocation': RecordRef(internalId=netsuite_location_id),
            'account': RecordRef(internalId=Utils.get_netsuite_config()['inventory_adjustment_account_id']),
            'inventoryList': {
                'inventory': overage_items
            }
        }

    return item_receipt, inventory_adjustment


async def map_received_items(received_items, receiving_store_location_id, item_fulfillment_items):
    overage_items = []
    mapped_received_items = []
    for item in item_fulfillment_items:
        asn_item = next((asn_item for asn_item in received_items if item['itemName'] == asn_item['product_id']), {})

        received_item = {
            'item': RecordRef(internalId=item['item']['internalId']),
            'location': RecordRef(internalId=receiving_store_location_id),
            'quantity': 0 if not asn_item else asn_item['quantity'],
            'itemReceive': True,
            # orderLine for an item receipt is always 1 higher than the line of the respective fulfillment item
            # (2 higher than the transfer order)
            'orderLine': int(item['orderLine']) + 1
        }

        if received_item['quantity'] > 0:
            if received_item['quantity'] > item['quantity']:
                # In case of overage, we utilize the expected quantity and fill overage item
                overage_items.append({
                    'adjustQtyBy': received_item['quantity'] - item['quantity'],
                    'item': received_item['item'],
                    'location': received_item['location']
                })

            mapped_received_items.append(received_item)

    return mapped_received_items, overage_items
