import aiobotocore
from aiobotocore.session import get_session
import logging
import asyncio

logger = logging.getLogger(__name__)


class SqsHandler:
    def __init__(self, queue_name, queue_url=None, profile_name=None):
        """
        Construct sqs wrapper obj
        :param queue_name:
        """
        self.queue_name = queue_name
        self.profile_name = profile_name
        self.session = get_session()
        self.sqs_url = queue_url

    async def load_queues_info(self):
        if not self.sqs_url:
            self.sqs_url = await self.get_sqs_queue_url()

    async def get_sqs_queue_url(self):
        async with self.session.create_client('sqs') as client:
            return (await client.get_queue_url(QueueName=self.queue_name))['QueueUrl']

    async def push_message(self, message):
        """
        Push message into sqs queue
        :param message:
        :return response:
        """
        response = None
        try:
            logger.info('Drop message to queue {queue_name}'.format(
                queue_name=self.queue_name))
            await self.load_queues_info()
            if message:
                async with self.session.create_client('sqs') as client:
                    response = await client.send_message(
                        MessageBody=message,
                        QueueUrl=self.sqs_url
                    )
                    logger.info('Pushed message %s into queue %s' %
                                (response.get('MessageId'), self.queue_name))
            else:
                logger.error(
                    'Cannot push message into %s; Message not defined' % self.queue_name)
        except Exception as ex:
            logger.exception(ex)

        return response

    async def get_message(self):
        """
        Pull message from sqs queue
        :return message:
        """
        message = None
        try:
            await self.load_queues_info()
            async with self.session.create_client('sqs') as client:
                message = await client.receive_message(
                    QueueUrl=self.sqs_url,
                    AttributeNames=[
                        'SentTimestamp'
                    ],
                    MaxNumberOfMessages=1,
                    MessageAttributeNames=[
                        'All'
                    ],
                    WaitTimeSeconds=5
                )
        except Exception as ex:
            logger.exception(ex)
            raise
        return message

    async def delete_message(self, receipt_handle):
        """
        Delete message from sqs queue
        :param receipt_handle:
        """
        try:
            await self.load_queues_info()
            async with self.session.create_client('sqs') as client:
                return await client.delete_message(
                    QueueUrl=self.sqs_url,
                    ReceiptHandle=receipt_handle
                )
                logger.info('Deleted message %s from queue %s' %
                            (receipt_handle, self.queue_name))
        except Exception as ex:
            logger.exception(ex)
            raise

    async def get_messages_count(self):
        """
        Get number of messages enqueued
        """
        try:
            await self.load_queues_info()
            async with self.session.create_client('sqs') as client:
                response = await client.get_queue_attributes(
                    QueueUrl=self.sqs_url,
                    AttributeNames=[
                        'ApproximateNumberOfMessages'
                    ]
                )
                nr_of_messages = response['Attributes']['ApproximateNumberOfMessages']
                logger.info('Number of messages still to be processed %s from queue %s' % (
                    nr_of_messages, self.queue_name))
                return int(nr_of_messages)
        except Exception as ex:
            logger.exception(ex)
            raise
