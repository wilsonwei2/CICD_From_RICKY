from lambda_utils.S3.S3Handler import S3Handler
from lambda_utils.newstore_api.jobs_manager import JobsManager
from lambda_utils.events.events_handler import EventsHandler
from shopify_import_products.transformers.transform import transform_products
from shopify_import_products.dynamodb import get_dynamodb_resource, get_item, update_item
from shopify_import_products.shopify.graphql import ShopifyAPI
from shopify_import_products.shopify.param_store_config import ParamStoreConfig
import logging
import os

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)

TRIGGER_NAME = str(os.environ.get('shopify_import_products_trigger', 'shopify_import_products_trigger'))

TENANT = os.environ.get('TENANT') or 'frankandoak'
STAGE = os.environ.get('STAGE') or 'x'
REGION = os.environ.get('REGION') or 'us-east-1'
CUSTOM_SIZE_MAPPING = ParamStoreConfig(TENANT, STAGE, REGION).get_shopify_custom_size_mapping()


def run(env_variables):
    dynamodb = get_dynamodb_resource()
    events_handler = EventsHandler()
    shopify_api = ShopifyAPI()

    try:
        item = get_item(os.environ['dynamo_table_name'], {'id': 'USC'}, dynamodb)
        if not item or item['update_status'] != 'RUNNING':
            if shopify_api.start_bulk_operation():
                LOGGER.info('Shopify bulk operation created')
                update_dynamodb(dynamodb, 'RUNNING')
                update_event_trigger(events_handler, 'rate(10 minutes)')
            else:
                LOGGER.error('Failed to start Shopify bulk operation')
                update_event_trigger(events_handler, 'rate(10 minutes)')
            return

        bulk_operation_status = shopify_api.current_bulk_operation()

        if bulk_operation_status == 'RUNNING':
            LOGGER.info('Waiting for Shopify bulk operation to complete')
            update_event_trigger(events_handler, 'rate(10 minutes)')
        elif bulk_operation_status == 'COMPLETED':
            products_text = shopify_api.get_products_text()

            if products_text:
                update_dynamodb(dynamodb, 'COMPLETED')
                update_event_trigger(events_handler, os.environ['cron_expression_for_next_day'])

                LOGGER.info('Starting product import')
                is_full = os.environ.get('is_full', 'false').lower() == 'true'
                import_products(products_text, env_variables, is_full)
                import_products(products_text, env_variables, locale='fr-CA')
            else:
                LOGGER.error(f'Shopify did not return any products.')
                update_event_trigger(events_handler, 'rate(10 minutes)')
        else:
            LOGGER.error(f'Shopify returned invalid bulk operation status:\n{bulk_operation_status}')
            update_event_trigger(events_handler, 'rate(10 minutes)')

    except Exception as error: # pylint: disable=W0703
        LOGGER.error(f'Error while importing products: {str(error)}', exc_info=True)
        # If there are too many requests already, start the next day
        if '429' in str(error):
            update_dynamodb(dynamodb, 'COMPLETED')
            update_event_trigger(events_handler, os.environ['cron_expression_for_next_day'])
        else:
            update_event_trigger(events_handler, 'rate(10 minutes)')


def import_products(text, env_variables, is_full=False, locale=None):
    products_per_file = int(os.environ.get('products_per_file', '1000'))
    products_slices, categories = transform_products(text, products_per_file, CUSTOM_SIZE_MAPPING, locale)
    run_full_import = is_full

    s3_bucket = os.environ['s3_bucket']
    s3_bucket_key = os.environ['s3_bucket_key']

    for products in products_slices:
        if products['items']:
            s3_handler = S3Handler(bucket_name=s3_bucket, key_name=s3_bucket_key)
            source_uri = f'https://{s3_bucket}/{s3_bucket_key}'
            jobs_manager_products = JobsManager(env_variables, 'products', s3_handler, source_uri, False)
            LOGGER.info(f'Sending products to the import_api (full: {run_full_import})')
            do_job(jobs_manager_products, products, run_full_import)
            run_full_import = False # IMPORTANT: only the first job that is started should be a full import

    if categories['items']:
        s3_handler = S3Handler(bucket_name=s3_bucket, key_name=s3_bucket_key)
        source_uri = f'https://{s3_bucket}/{s3_bucket_key}'
        jobs_manager_categories = JobsManager(env_variables, 'categories', s3_handler, source_uri, False)
        LOGGER.info(f'Sending categories to the import_api (full: {run_full_import})')
        do_job(jobs_manager_categories, categories, run_full_import)


def do_job(jobs_manager, data_dict, is_full):
    transformed_uri = jobs_manager.create_file(data_dict)
    LOGGER.info(f'Transformed URI: {transformed_uri}')
    # replace transformed_uri with generated URL from to get 'key-name' from 'bucket-name'
    s3_handler = S3Handler(
        bucket_name=os.environ['s3_bucket'],
        key_name='/'.join(transformed_uri.split("/")[-2:])
    )
    transformed_uri = s3_handler.getS3().generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': os.environ['s3_bucket'],
            'Key': '/'.join(transformed_uri.split("/")[-2:])
        },
        ExpiresIn=86400
    )
    import_job = jobs_manager.create_job(is_full)
    jobs_manager.start_job(import_job, transformed_uri)
    LOGGER.info(f'Generated presigned transformed URL: {transformed_uri}')


def update_dynamodb(dynamodb, update_status):
    LOGGER.info('Updating dynamo table -- save state')
    update_item(os.environ['dynamo_table_name'], {
        'Key': {
            'id': 'USC'
        },
        'UpdateExpression': 'set update_status = :update_status',
        'ExpressionAttributeValues': {
            ':update_status': update_status
        },
        'ReturnValues': 'UPDATED_NEW'
    }, dynamodb)


def update_event_trigger(events_handler, trigger_expression):
    LOGGER.info(f'Updated the trigger event at {trigger_expression}')
    events_handler.update_trigger(TRIGGER_NAME, trigger_expression, True)
