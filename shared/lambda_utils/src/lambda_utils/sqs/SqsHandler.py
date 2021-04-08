import boto3
import logging

logger = logging.getLogger(__name__)


class SqsHandler:
    def __init__(self, queue_name, profile_name=None):
        """
        Construct sqs wrapper obj
        :param queue_name:
        """
        self.queue_name = queue_name
        self.session = boto3.Session(profile_name=profile_name)
        self.client = self.session.client('sqs')
        self.sqs_queue = self.get_sqs_queue()
        self.queue_url = self.get_sqs_queue_url()

    def get_sqs_queue_url(self):
        return self.client.get_queue_url(QueueName=self.queue_name)['QueueUrl']

    def get_sqs_queue(self):
        """
        Retrieve sqs queue given name
        :param queue_name:
        :return sqs_queue:
        """
        return self.session.resource('sqs').get_queue_by_name(QueueName=self.queue_name)

    def push_message(self, message_group_id=None, message=None):
        """
        Push message into sqs queue
        :param message:
        :return response:
        """
        response = None
        try:
            if message:
                if message_group_id:
                    response = self.sqs_queue.send_message(MessageGroupId=message_group_id, MessageBody=message)
                else:
                    response = self.sqs_queue.send_message(MessageBody=message)
                logger.info('Pushed message %s into queue %s' % (response.get('MessageId'), self.queue_name))
            else:
                logger.error('Cannot push message into %s Message not defined' % self.queue_name)
        except Exception as ex:
            logger.exception(ex)
            raise ex

        return response


    """
    Push a list of Messages
    """
    def push_messages(self, messages_list):
        """
        Push message into sqs queue
        :param message:
        :return response:
        """
        response = None
        messages = [{'Id': str(msg['id']), 'MessageBody': str(msg['id'])} for msg in messages_list]
        try:
            if messages:
                response = self.client.send_message_batch(
                    Entries=messages,
                    QueueUrl=self.queue_url
                )
                logger.info('Pushed message %s into queue %s' %
                            (response.get('MessageId'), self.queue_name))
            else:
                logger.error(
                    'Cannot push message into %s Message not defined' % self.queue_name)
        except Exception as ex:
            logger.exception(ex)

        return response


    def get_message(self, max_number_of_messages=1, wait_time_seconds=5):
        """
        Pull message from sqs queue
        :return message:
        """
        message = None
        try:
            message = self.client.receive_message(
                QueueUrl=self.queue_url,
                AttributeNames=[
                    'SentTimestamp'
                ],
                MaxNumberOfMessages=max_number_of_messages,
                MessageAttributeNames=[
                    'All'
                ],
                WaitTimeSeconds=wait_time_seconds
            )
        except Exception as ex:
            logger.exception(ex)
            raise Exception(ex)
        return message

    def delete_message(self, receipt_handle):
        """
        Delete message from sqs queue
        :param receipt_handle:
        """
        try:
            return self.client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            logger.info('Deleted message %s from queue %s' % (receipt_handle, self.queue_name))
        except Exception as ex:
            logger.exception(ex)
            raise Exception(ex)

    def get_messages_count(self):
        """
        Get number of messages enqueued
        """
        try:
            response = self.client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=[
                    'ApproximateNumberOfMessages'
                ]
            )
            nr_of_messages = response['Attributes']['ApproximateNumberOfMessages']
            logger.info('Number of messages still to be processed %s from queue %s' % (nr_of_messages, self.queue_name))
            return int(nr_of_messages)
        except Exception as ex:
            logger.exception(ex)
            raise Exception(ex)
