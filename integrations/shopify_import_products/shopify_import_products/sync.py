import os
import json
import logging
# Libs from shared
from lambda_utils.S3.S3Handler import S3Handler
from lambda_utils.newstore_api.jobs_manager import JobsManager
from lambda_utils.events.events_handler import EventsHandler
# Local imports
from shopify_import_products.shopify.products import get_products
from shopify_import_products.transformers.transform import transform_products
from shopify_import_products.dynamodb import get_dynamodb_resource, get_item, update_item

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)

LIMIT = str(os.environ.get('products_per_page', '20'))
FILTER_PRODUCT_TABLE = {}
S3_LINK_LIFE = 86400 # 24 hours
TRIGGER_NAME = str(os.environ.get('shopify_import_products_trigger', 'shopify_import_products_trigger'))

# List of products to import where the key is the SKU (product_id on  NewStore)
# and stores the product id and variant id from Shopify, utilized to verify
# if there are duplicated SKUs (product_id on  NewStore)
# Format: {'SKU001': {'variant_id': '100', 'product_id': '110'}}
PRODUCTS_TO_IMPORT = {}
DUPLICATED_PRODUCTS = {}


def run(env_variables):
    products = []
    categories = None
    dynamodb = get_dynamodb_resource()
    events_handler = EventsHandler()
    try:
        shopify_products, last_page, next_page = import_products(dynamodb)
        if shopify_products:
            products, categories = transform_products(shopify_products)
            LOGGER.info(f'Products to import. \n {json.dumps(products, indent=4)}')

            # To run an Full import -- Change the environment to true and
            # update dynamodb table to 1
            is_full = os.environ.get('is_full', 'False')
            is_full = bool(is_full.lower() in ['1', 'true'] and not last_page)

            if products['items']:
                s3_handler = S3Handler(bucket_name=os.environ['s3_bucket'], key_name=os.environ['s3_bucket_key'])
                source_uri = f"https://{os.environ['s3_bucket']}/{os.environ['s3_bucket_key']}"
                jobs_manager_products = JobsManager(
                    env_variables, "products", s3_handler, source_uri, False)
                LOGGER.info('Sending products to the import_api')
                do_job(jobs_manager_products, products, is_full)

            if categories['items']:
                s3_handler = S3Handler(bucket_name=os.environ['s3_bucket'], key_name=os.environ['s3_bucket_key'])
                source_uri = f"https://{os.environ['s3_bucket']}/{os.environ['s3_bucket_key']}"
                jobs_manager_categories = JobsManager(
                    env_variables, "categories", s3_handler, source_uri, False)
                LOGGER.info('Sending categories to the import_api')
                do_job(jobs_manager_categories, categories, is_full)

            # After everything finishes we save to dynamo the next_page and last_updated_at
            update_dynamodb(dynamodb, next_page,
                            shopify_products[-1]['updated_at'])

            # Trigger the lambda again in 10 minutes
            update_event_trigger(events_handler, 'rate(10 minutes)')

        if shopify_products is not None and ((last_page and not next_page) or (not last_page and not next_page)):
            # If nothing comes it means all products were imported,
            # so we put next_page to None on dynamodb and update the trigger expression
            item = get_item(os.environ['dynamo_table_name'], {'id': 'USC'}, dynamodb)

            # While the lambda runs, cur_updated_at is used to fetch paged data on Shopify, so that value must not change
            # On the other hand last_updated_at always changes to the latest updated_at of the last product
            # When the lambda finishes the last_page is set to 0 and cur_updated_at receives the last_updated_at value
            update_dynamodb(dynamodb, None, None, item['last_updated_at'])

            cron_expression = os.environ['cron_expression_for_next_day']
            update_event_trigger(events_handler, cron_expression)
    except Exception as ex: # pylint: disable=W0703
        LOGGER.error(f"Error while importing products: {str(ex)}", exc_info=True)
        # Make sure the lambda is triggered again in 10 minutes since there was an error this time
        update_event_trigger(events_handler, 'rate(10 minutes)')


def _append_if_exists(array, value, name):
    if value:
        array.append({
            "name": name,
            "value": str(value)
            })


def do_job(jobs_manager, array, is_full):
    try:
        transformed_uri = jobs_manager.create_file(array)
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
    except Exception as e:
        raise Exception(e)


def import_products(dynamodb):
    '''
    Function that is used to check the last run of the import job, and fetch the products
    after the previous run.
    '''
    global DUPLICATED_PRODUCTS, PRODUCTS_TO_IMPORT # pylint: disable=W0603
    published_status = os.environ.get('product_published_status', 'published')
    params = {
        'limit': LIMIT,
        'order': 'updated_at asc',
        'published_status': published_status
    }

    next_page = None
    # Here we get next_page and last_updated_at from dynamodb
    item = get_item(os.environ['dynamo_table_name'], {'id': 'USC'}, dynamodb)
    if item:
        next_page = item.get('next_page')
        updated_at = item.get('cur_updated_at')
        if updated_at:
            params['updated_at_min'] = updated_at

        # Get duplicated_products stored from previous runs
        DUPLICATED_PRODUCTS = item.get('duplicated_products', {})
        PRODUCTS_TO_IMPORT = read_products_to_import_from_s3()
    else:
        DUPLICATED_PRODUCTS = {}
        PRODUCTS_TO_IMPORT = {}

    # Then we get the products
    # Only bring the products that are created on or after 8/5/2015
    params['created_at_min'] = os.environ.get('created_at_min', '2015-05-08T00:00:00-00:00')
    return get_products(params, next_page)


def update_dynamodb(dynamodb, next_page, last_updated_at=None, cur_updated_at=None):
    update_expression = "set next_page = :lp, duplicated_products=:dp"
    if last_updated_at:
        update_expression += ", last_updated_at=:lu"
    if cur_updated_at:
        update_expression += ", cur_updated_at=:cu"

    expression_attributes = {
        ':lp': next_page if next_page else None,
        ':dp': DUPLICATED_PRODUCTS
    }
    if last_updated_at:
        expression_attributes[':lu'] = last_updated_at
    if cur_updated_at:
        expression_attributes[':cu'] = cur_updated_at

    schema = {
        'Key': {
            'id': 'USC'
        },
        'UpdateExpression': update_expression,
        'ExpressionAttributeValues': expression_attributes,
        'ReturnValues': "UPDATED_NEW"
    }
    LOGGER.info('Updating dynamo table -- save state')
    update_item(os.environ['dynamo_table_name'], schema, dynamodb)


def update_event_trigger(events_handler, trigger_expression):
    LOGGER.info(f'Updated the trigger event at {trigger_expression}')
    events_handler.update_trigger(TRIGGER_NAME, trigger_expression, True)


def read_products_to_import_from_s3():
    filter_file_name = 'tmp/import_products/products_list.json'
    s3_handler = S3Handler(bucket_name=os.environ['s3_bucket'], key_name=filter_file_name)
    if s3_handler.validate_exists():
        LOGGER.info('Product list already exists on S3, using it...')
        return json.loads(s3_handler.getS3File()['data'])
    LOGGER.info('Product list does not exisit at S3. Utilizing empty list...')
    return {}
