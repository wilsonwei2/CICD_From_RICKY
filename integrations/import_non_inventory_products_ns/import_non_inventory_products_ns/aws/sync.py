import logging
import os

from lambda_utils.S3.S3Handler import S3Handler
from lambda_utils.newstore_api.jobs_manager import JobsManager

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)

S3_BUCKET_KEY = os.environ['s3_bucket_key']
S3_BUCKET = os.environ['s3_bucket']

IMPORT_TYPES = ['products', 'prices', 'availabilities']


def run(env_variables):
    s3_handler = S3Handler(bucket_name=S3_BUCKET, key_name=S3_BUCKET_KEY)
    source_uri = f's3://{S3_BUCKET}/{S3_BUCKET_KEY}'

    for import_type in IMPORT_TYPES:
        jobs_manager = JobsManager(env_variables, import_type, s3_handler, source_uri, False)
        LOGGER.info(f'Sending non inventory {import_type} to the import_api')

        transformed_uri = s3_handler.get_presigned_url(f'non-inventory-{import_type}.json.zip')
        LOGGER.info(f'Transformed URI: {transformed_uri}')

        import_job = jobs_manager.create_job(False)
        jobs_manager.start_job(import_job, transformed_uri)
