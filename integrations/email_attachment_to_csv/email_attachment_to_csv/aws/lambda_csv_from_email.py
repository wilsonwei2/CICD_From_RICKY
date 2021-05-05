# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016 NewStore, Inc. All rights reserved.
import os
import json
import boto3
import logging
import email
from email.policy import SMTPUTF8

S3 = boto3.resource('s3')
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
S3_PREFIX = os.environ['S3_PREFIX']
## This is the variable that is used to say that it is in 'imported_CSV'
S3_BUCKET = os.environ['S3_BUCKET']


def handler(event, context): # pylint: disable=W0613
    LOGGER.info('Function Invoked by Email')
    LOGGER.info(f"Event: {json.dumps(event, indent=4)}")

    for record in event['Records']:
        if not record['eventName'].startswith('ObjectCreated:'):
            LOGGER.error(f"Incorrect eventName received: {record['eventName']}")
            return

        s3_obj = S3.Object(record['s3']['bucket']['name'], record['s3']['object']['key'])
        message = email.message_from_bytes(s3_obj.get()['Body'].read(),
                                           policy=SMTPUTF8)

        for attachment in message.iter_attachments():
            content = attachment.get_content()
            if isinstance(content, str):
                content = content.encode('utf-8')

            ## The extraction process is the same.
            key = f"{S3_PREFIX}{attachment.get_filename()}"
            LOGGER.info(f'The file name is {key}')
            s3_out_obj = S3.Bucket(S3_BUCKET).put_object(Key=key, Body=content)
            LOGGER.info(f'Uploaded {s3_out_obj}')
