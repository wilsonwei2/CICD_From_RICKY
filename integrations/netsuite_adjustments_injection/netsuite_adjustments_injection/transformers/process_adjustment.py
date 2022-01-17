import logging
import netsuite_adjustments_injection.helpers.util as util
from netsuite_adjustments_injection.helpers.exceptions import StoreMappingException
from netsuite.service import RecordRef

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)


def transform_inventory_transfer(adjustment_event, products_info, store):
    store_country_code = util.get_one_of_these_fields(obj=store['physical_address'],
                                                      fields=['country', 'country_code'])
    currency_id = util.get_currency_from_country_code(country_code=store_country_code)
    subsidiary_id = util.get_subsidiary_from_currency(currency_id)

    fulfillment_node_id = adjustment_event['fulfillment_node_id']
    fulfillment_location_id = util.get_nws_location_id(fulfillment_node_id)

    if not fulfillment_location_id:
        raise StoreMappingException(f"fulfillment_location_id, {fulfillment_location_id}, isn't mapped to NetSuite")

    from_location_id = get_from_location(adjustment_event, fulfillment_location_id)

    if not from_location_id:
        raise StoreMappingException(f"Location {adjustment_event['origin_stock_location_name']} isn't mapped to NetSuite")

    # Decide here the to_location (main, damaged or write off retail/warehouse)
    # FAO Doesn't use write off, for now it just handles main and damaged locations
    to_location_id = None
    if 'destination_stock_location_name' in adjustment_event:
        if adjustment_event['destination_stock_location_name'].lower() == 'main':
            to_location_id = util.get_netsuite_store_internal_id(fulfillment_location_id)
        elif adjustment_event['destination_stock_location_name'].lower() == 'damaged':
            to_location_id = util.get_netsuite_store_internal_id(fulfillment_location_id, False)
        #elif adjustment_event['destination_stock_location_name'].lower() == 'retail_write_off':
        #    to_location_id = util.get_write_off_from_subsidiary(subsidiary_id, 'retail')
        #elif adjustment_event['destination_stock_location_name'].lower() == 'warehouse_write_off':
        #    to_location_id = util.get_write_off_from_subsidiary(subsidiary_id, 'warehouse')
    else:
        if 'damage' in adjustment_event['adjustment_type'].lower():
            if adjustment_event['origin_stock_location_name'].lower() == 'main':
                to_location_id = util.get_netsuite_store_internal_id(fulfillment_location_id, False)
            else:
                to_location_id = util.get_netsuite_store_internal_id(fulfillment_location_id)

    if not to_location_id:
        raise StoreMappingException(f"Location {adjustment_event.get('destination_stock_location_name')} isn't mapped to NetSuite")

    tran_date = util.format_datestring_for_netsuite(date_string=adjustment_event['processed_at'],
                                                    time_zone=store['timezone'])

    return {
        'location': RecordRef(internalId=from_location_id),
        'transferLocation': RecordRef(internalId=to_location_id),
        'memo': ' - '.join(filter(None, [adjustment_event.get('adjustment_reason'), adjustment_event.get('note')])),
        'subsidiary': RecordRef(internalId=subsidiary_id),
        'tranDate': tran_date.date(),
        'inventoryList': {
            'inventory': [
                {
                    'item': RecordRef(internalId=item['netsuite_internal_id']),
                    'adjustQtyBy': item['quantity']
                } for item in products_info
            ]
        }
    }


def get_from_location(adjustment_event, fulfillment_location_id):
    # Decide here the from_location (main, damaged or write off retail/warehouse)
    # FAO Doesn't use write off, for now it just handles main and damaged locations
    from_location_id = None

    if adjustment_event['origin_stock_location_name'].lower() == 'main':
        from_location_id = util.get_netsuite_store_internal_id(fulfillment_location_id)
    elif adjustment_event['origin_stock_location_name'].lower() == 'damaged':
        from_location_id = util.get_netsuite_store_internal_id(fulfillment_location_id, False)
    #elif adjustment_event['origin_stock_location_name'].lower() == 'retail_write_off':
    #    from_location_id = util.get_write_off_from_subsidiary(subsidiary_id, 'retail')
    #elif adjustment_event['origin_stock_location_name'].lower() == 'warehouse_write_off':
    #    from_location_id = util.get_write_off_from_subsidiary(subsidiary_id, 'warehouse')

    return from_location_id
