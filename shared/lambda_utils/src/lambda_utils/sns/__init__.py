# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016 NewStore, Inc. All rights reserved.
import os
import json
import logging
import boto3

logger = logging.getLogger(__name__)


def sns_wrapper(event):
    """
    Start of the lambda handler
    :param event: this lambda is triggered daily
    :param context: function context
    :return:
    """
    # Get Lambda function specific variables from the bucket
    event.update(dict(os.environ))
    logger.debug(json.dumps(event, indent=4))

    session = boto3.Session(profile_name=event.get('profile_name'))
    sns = session.client('sns')
    topicArn = event['sns_topic_arn']
    message = json.dumps(event)

    # Send message (containing all tenant specific params) to SNS.
    try:
        sns.publish(
            TopicArn=topicArn,
            Message=message
        )
    except Exception as ex:
        raise(Exception(ex))
