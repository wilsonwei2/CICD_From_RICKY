import json
import logging
import falcon
import boto3
import os

from cycle_counts.api.cycle_count_eventstream_listener import CycleCountEventStreamListener
from cycle_counts.aws.config import get_queue_name, get_eventstream_api_key

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class Middleware:
    def process_request(self, req, _):
        LOGGER.info(f'Request url: {req.url} - method: {req.method} - body: {json.dumps(req.media, indent=4)}')


APP = falcon.API(middleware=Middleware())


def api_setup():
    sqs_client = boto3.client('sqs')
    queue_name = get_queue_name()
    cycle_count_event_listener = CycleCountEventStreamListener(queue_name=queue_name, api_key=get_eventstream_api_key(),
                                                               sqs_client=sqs_client)
    stage = os.environ.get('STAGE')
    APP.add_route(f'/{stage}/eventstream', cycle_count_event_listener)


api_setup()
