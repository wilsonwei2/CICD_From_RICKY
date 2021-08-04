from datetime import datetime
import uuid


class PaymentConnector():
    def perform_authorization(self, event_body):
        # Call here PSP
        return {
            "transaction_id": event_body['idempotency_key'],
            "instrument_id": event_body['arguments']['instrument']['type'] + event_body['arguments']['instrument']['identifier'],
            "capture_amount": event_body['arguments']['amount'],
            "currency": event_body['arguments']['currency'],
            "created_at":  event_body['metadata']['processed_at']+'Z',
            "processed_at": event_body['metadata']['processed_at']+'Z'
        }

    def perform_capture(self, event_body):
        now_date_time_string = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        request_instrument_id = event_body['transactions'][0]['instrument_id']
        request_transaction_id = event_body['transactions'][0]['transaction_id']

        return {
            "transaction_id": request_transaction_id + str(uuid.uuid4()) + "-capture",
            "instrument_id": request_instrument_id,
            "capture_amount": event_body['arguments']['amount'] * -1,
            "refund_amount": event_body['arguments']['amount'],
            "currency": event_body['arguments']['currency'],
            "created_at": now_date_time_string,
            "processed_at": now_date_time_string,
        }

    def perform_refund(self, event_body):
        now_date_time_string = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        request_instrument_id = event_body['transactions'][0]['instrument_id']
        request_transaction_id = event_body['transactions'][0]['transaction_id']
        return {
            "transaction_id": request_transaction_id + str(uuid.uuid4()) + "-refund",
            "instrument_id": request_instrument_id,
            "capture_amount": 0,
            "refund_amount": event_body['arguments']['amount'] * -1,
            "currency": event_body['arguments']['currency'],
            "created_at": now_date_time_string,
            "processed_at": now_date_time_string,
        }

    def perform_revoke(self, event_body):
        now_date_time_string = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        request_instrument_id = event_body['transactions'][0]['instrument_id']
        request_transaction_id = event_body['transactions'][0]['transaction_id']
        return {
            "transaction_id": request_transaction_id + str(uuid.uuid4()) + "-revoke",
            "instrument_id": request_instrument_id,
            "capture_amount": event_body['arguments']['amount'] * -1,
            "refund_amount": 0,
            "currency": event_body['arguments']['currency'],
            "created_at": now_date_time_string,
            "processed_at": now_date_time_string,
        }
