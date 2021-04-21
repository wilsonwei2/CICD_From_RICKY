import json
import logging
from dacite import from_dict
from newstore_common.newstore import create_ns_connector

from cycle_counts.aws.config import get_netsuite_newstore_service, get_netsuite_client, get_lambda_parameters
from cycle_counts.models.ns_import_count_task import NewStoreInventoryCountEvent


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def handler(event, context):
    LOGGER.info(f'Event: {event}')
    netsuite_client = get_netsuite_client()
    netsuite_newstore_service = get_netsuite_newstore_service()
    newstore_connector = create_ns_connector(context, get_lambda_parameters())

    if len(event.get('Records')) > 1:
        raise Exception(f"Update NetSuite Inventory failed, more than one record found in event: {event.get('Records')}")

    message = json.loads(event.get('Records')[0].get('body'))
    message['ns_id'] = message.pop('id')
    LOGGER.info(f'Message: {message}')
    ns_count_event = from_dict(data=message, data_class=NewStoreInventoryCountEvent)
    ns_inv_count = newstore_connector.get_inventory_count_task(ns_count_event.ns_id)
    if ns_inv_count['status'] != 'completed':
        LOGGER.info(f'Inventory Count status is not completed. Id: {ns_count_event.ns_id} Status: {ns_inv_count["status"]}')
        return

    netsuite_items = netsuite_newstore_service.transf_event_to_netsuite_items(ns_count_event.items)
    resp = netsuite_client.inventory_count_update(transaction_id=ns_inv_count['external_id'], items=netsuite_items)

    item = resp.inventory_count[0]
    if item.update_status.get('status') == 'Success':
        LOGGER.info(f'NetSuite inventory count with transaction number {item.transaction_id} updated with success')
    else:
        raise Exception(f'NetSuite inventory count with transaction number {item.transaction_id}'
                        f'failed payload error: {item.update_status}')
