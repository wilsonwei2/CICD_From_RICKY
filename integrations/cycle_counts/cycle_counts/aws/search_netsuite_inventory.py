import logging

from dataclasses import asdict

from cycle_counts.aws.config import get_netsuite_client, get_netsuite_newstore_service, get_lambda_parameters
from cycle_counts.models.ns_import_count_task import ImportCountTask
from newstore_common.newstore import create_ns_connector


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def handler(_, context):
    netsuite_client = get_netsuite_client()
    resp = netsuite_client.inventory_count_search()

    if len(resp.inventory_count) == 0:
        LOGGER.info(f'No results to process')
        return

    newstore_connector = create_ns_connector(context, get_lambda_parameters())
    newstore_connector.raise_errors = True
    netsuite_newstore_service = get_netsuite_newstore_service()

    for search_count in resp.inventory_count:
        import_count_task = netsuite_newstore_service.create_import_count_task(search_count)
        store_id = netsuite_newstore_service.get_store_id(int(search_count.search_payload.location.internalid))
        try:
            ns_resp = newstore_connector.create_inventory_count_task(store_id, asdict(import_count_task))
        except Exception as e: # pylint: disable=broad-except
            LOGGER.info(f'Exception received {str(e)}')

            ns_resp = None
            if 'product_not_reachable' in str(e):
                LOGGER.info('Recover from error and create task with products that exist')
                import_count_task = _remove_non_existent_products(import_count_task, str(e))
                if len(import_count_task.product_ids) > 0:
                    ns_resp = newstore_connector.create_inventory_count_task(store_id, asdict(import_count_task))

        if ns_resp is None or not ns_resp.get('success'):
            LOGGER.info(f'Task with transaction id: {search_count.transaction_id} was not inserted')
            continue
        LOGGER.info(f'Task with transaction id: {search_count.transaction_id} was inserted successfully')


def _remove_non_existent_products(import_count_task: ImportCountTask, error: str) -> ImportCountTask:
    failed_items = []
    for item in import_count_task.product_ids:
        if item in error:
            failed_items.append(item)

    for item in failed_items:
        LOGGER.info(f'Remove item - SKU: {item} from count task because does not exist in NewStore')
        import_count_task.product_ids.remove(item)
    return import_count_task
