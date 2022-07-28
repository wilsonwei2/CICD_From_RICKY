import unittest
import asyncio
from unittest.mock import patch


class TestFrankAndOakEventStreamReceiver(unittest.TestCase):
    def setUp(self):
        self.variables = {
            'SQS_CASH_SALE': 'SQS_CASH_SALE',
            'SQS_SALES_ORDER': 'SQS_SALES_ORDER',
            'SQS_TRANSFER_ORDER_QUEUE': 'SQS_TRANSFER_ORDER_QUEUE',
            'SQS_INVENTORY_TRANSFER': 'SQS_INVENTORY_TRANSFER',
            'SQS_RETURN_PROCESSED': 'SQS_RETURN_PROCESSED',
            'SQS_FULFILLMENT_ASSIGNED': 'SQS_FULFILLMENT_ASSIGNED'
        }
        self.os_env = patch.dict('os.environ', self.variables)
        self.os_env.start()
        from netsuite_event_stream_receiver.aws.receive_events import handler
        self.handler = handler

    @patch('netsuite_event_stream_receiver.aws.receive_events.push_message_to_sqs', autospec=True)
    def test_handler(self, mock_push_message_to_sqs):
        event = {
            "body": "{\"payload\": {},\"published_at\": \"\",\"name\": \"return.processed\"}"
        }
        self.handler(event, None)
        mock_push_message_to_sqs.assert_called_with('SQS_RETURN_PROCESSED', {'payload': {'published_at': ''}})
