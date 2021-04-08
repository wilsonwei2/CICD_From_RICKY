import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ErrorReports(object):
    
    def __init__(self, params):
        self.sender = params['email_sender']
        self.recipients = params['email_recipients'].split(' ')
        self.charset = "UTF-8"
        self.client = boto3.client('ses')

    def send_error_report(self, subject, body):
        if filter(None, self.recipients):
            try:
                #Provide the contents of the email.
                response = self.client.send_email(
                    Destination={
                        'ToAddresses': self.recipients,
                    },
                    Message={
                        'Body': {
                            'Text': {
                                'Charset': 'UTF-8',
                                'Data': body,
                            },
                        },
                        'Subject': {
                            'Charset': self.charset,
                            'Data': subject,
                        },
                    },
                    Source=self.sender,
                )
            # Display an error if something goes wrong. 
            except ClientError as e:
                logger.error('Error: %s' % (e.response['Error']['Message']))
            else:
                logger.info("Email sent! Message ID: %s" % (response['MessageId']))
                return True
        else:
            logger.info('No recipient informed.')
        return False
