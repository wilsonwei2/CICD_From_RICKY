import json
import logging


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class CycleCountEventStreamListener:
    def __init__(self, queue_name: str, api_key: str, sqs_client):
        self.queue_name = queue_name
        self.sqs_client = sqs_client
        self.api_key = api_key

    def on_post(self, req, resp):
        if not self._is_authorized(req.get_header('AUTHORIZATION')):
            LOGGER.info('Authorization failed')
            LOGGER.info(req.get_header('AUTHORIZATION'))
            resp.status = 403
            return resp
        event_body = req.media
        if event_body.get('name') != 'inventory_count.items_counted':
            resp.status = 200
            LOGGER.info(f'Ignoring event received event: {event_body.get("name")}')
            return resp

        payload = event_body.get('payload')
        if payload.get('chunk_number') != payload.get('total_chunks'):
            LOGGER.info(f'chunk_number: {payload.get("chunk_number")} is different then total_chunks: {payload.get("total_chunks")},'
                        f' event will be ignored.')
            resp.status = 200
            return resp

        queue_url = self.sqs_client.get_queue_url(QueueName=self.queue_name)
        self.sqs_client.send_message(QueueUrl=queue_url['QueueUrl'], MessageBody=json.dumps(payload))
        resp.status = 200
        return resp

    def _is_authorized(self, authorization: str) -> bool:
        if authorization == f'Bearer {self.api_key}':
            return True
        return False
