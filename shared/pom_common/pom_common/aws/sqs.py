import logging
import boto3

LOGGER = logging.getLogger(__name__)

def receive_messages(queue_name, region, result_limit=0, wait_time_seconds=0, message_attribute_names=[]):
    """ a generator that receives messages from a queue """

    last_message = 'init'
    sqs = boto3.resource("sqs", region)
    queue = sqs.get_queue_by_name(QueueName=queue_name) # pylint: disable=no-member
    cnt = 0
    while last_message is not None: # pylint: disable=too-many-nested-blocks
        messages = queue.receive_messages(
            MaxNumberOfMessages=10,
            WaitTimeSeconds=wait_time_seconds,
            MessageAttributeNames=message_attribute_names
        )
        msg_len = len(messages)
        LOGGER.debug(f"received {msg_len} messages from queue")
        if msg_len > 0:
            for message in messages:
                last_message = message
                cnt += 1

                yield last_message

                if result_limit != 0 and cnt >= result_limit:
                    LOGGER.debug(f"Reached process limit {result_limit} - stopping now")
                    last_message = None
                    break
        else:
            last_message = None
