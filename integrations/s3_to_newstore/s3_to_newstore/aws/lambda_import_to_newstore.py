import json
import os
from time import time
import logging
from urllib.parse import unquote
import boto3
from newstore_adapter.connector import NewStoreConnector

S3 = boto3.client('s3')
ENTITIES_CSV = os.environ['ENTITIES']
PROVIDER = os.environ['PROVIDER']
TENANT = os.environ['TENANT']
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.DEBUG)


def handler(event, context):
    """Import data into NewStore API from S3 queue.

    Queue is filled from `lambda_step_function.py` and this lambda is triggered
    from the S3 bucket itself. This is currently configured manually using the
    AWS console which triggers 1 of 2 instances of this lambda depending on
    which type of data is being imported. The two instances are defined using
    slightly different env vars in the cloudformation `template.yml`.

    Args:
        event: A dict triggered by S3 notification (e.g., https://docs.aws.amazon.com/lambda/latest/dg/with-s3-example.html
        #walkthrough-s3-events-adminuser-create-test-function-upload-zip-test-manual-invoke)
        context: Runtime info of type `LambdaContext`.

    Returns:
        nothing
    """
    LOGGER.info(f"Event: {json.dumps(event, indent=2)}")

    ns_handler = NewStoreConnector(tenant=TENANT, context=context)
    entities = [i.strip() for i in ENTITIES_CSV.split(',')]

    start_prev_received_imports(ns_handler, entities)

    for record in event['Records']:
        assert record['eventName'] in ('ObjectCreated:Put', 'ObjectCreated:Copy')

        s3_bucket_name = record['s3']['bucket']['name']
        s3_key = unquote(record['s3']['object']['key'])
        s3_params = {
            'Bucket': s3_bucket_name,
            'Key': s3_key
        }
        s3_link = S3.generate_presigned_url('get_object', Params=s3_params)

        # Import into newstore
        import_body = {
            'provider': PROVIDER,
            'source_uri': s3_link,
            'revision': int(time() * 1000),
            'entities': entities
        }
        ns_import = ns_handler.create_import(import_body)
        LOGGER.info(f'Created import {ns_import}')

        import_start_body = {
            'transformed_uri': s3_link
        }
        response = ns_handler.start_import(ns_import['id'], import_start_body)
        LOGGER.info('Started import')
        LOGGER.debug(json.dumps(response, indent=4))

# If an import job previously received was not started due to a timeout
# This function handles to start it
def start_prev_received_imports(ns_handler, entities):
    jobs_received = ns_handler.get_import_jobs_by_state('received')
    job_received_items = jobs_received.get('items', [])
    if not job_received_items:
        LOGGER.info('No previous imports to start')
    for job in job_received_items:
        if entities[0] == job['entities'][0]: # only process if entities are same, only works for one entity(!)
            LOGGER.info(f'Start previously received import {job}')
            job_details = ns_handler.get_import_job(job['import_id'])
            import_start_body = {
                'transformed_uri': job_details['source_uri']
            }
            response = ns_handler.start_import(job_details['import_id'], import_start_body)
            LOGGER.info('Started previously received import')
            LOGGER.debug(json.dumps(response, indent=4))
