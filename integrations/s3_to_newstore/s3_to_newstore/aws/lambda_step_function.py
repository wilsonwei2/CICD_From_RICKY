# import os
import json
import boto3
import logging

S3 = boto3.resource('s3')
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


def handler(event, context): # pylint: disable=W0613
    """Import queue for `lambda_import_to_newstore.py`.

    As a task for a step function, implements a queue system which moves ZIP files
    from one S3 location to another after a certain time in order to limit the input
    effects on NewStore import API calls.

    Args:
        event: A dict passed into the Step Function invoked from another Lambda
            function containing the following example format.
            { "bucket": "aninebing-x-0-newstore-dmz",
              "prefix": "queued_for_import",
              "chunk_prefix": "abc",
              "secs_between_chunks": 100}
        context: Runtime info of type `LambdaContext`.

    Returns:
        event: The same event received as input to be passed to the next step.

    Raises:
        Exception: If input `event` param is invalid or missing attributes.
    """
    LOGGER.debug(f'Event: {json.dumps(event)}')

    try:
        source_bucket = event['bucket']
        source_prefix = event['prefix']
        source_chunk_prefix = event['chunk_prefix']

        # dest_bucket = os.environ['DESTINATION_BUCKET']
        # dest_prefix = os.environ['DESTINATION_PREFIX']
        dest_bucket = event['dest_bucket']
        dest_prefix = event['dest_prefix']

        for s3obj in S3.Bucket(source_bucket).objects.filter(Prefix=source_prefix).limit(1):
            name_part = s3obj.key.split(source_chunk_prefix, maxsplit=1)[1]
            dest_key = f"{dest_prefix}{name_part}"
            copy_source = {
                'Bucket': s3obj.bucket_name,
                'Key': s3obj.key
            }
            S3.Object(dest_bucket, dest_key).copy_from(CopySource=copy_source)
            s3obj.delete()
            event['continue'] = True
            return event

        event['continue'] = False
        return event
    except Exception as err: # pylint: disable=W0703
        LOGGER.exception(err, exc_info=True)
        event['continue'] = False
        return event
