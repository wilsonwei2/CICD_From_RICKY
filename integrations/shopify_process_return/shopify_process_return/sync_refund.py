# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016 NewStore, Inc. All rights reserved.
import datetime
import logging
import os
import json
from shopify.shopify import ShopifyConnector
from lambda_utils.sqs.SqsHandler import SqsHandler
from utils import get_all_shopify_handlers

RETRIEVE_ORDERS_FROM_HOURS = int(os.environ.get('HOURS_TO_CHECK', '12'))

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

SQS_HANDLER = SqsHandler(os.environ['sqs_returns_name'])


def handler(event, context):
    """
    Start of the lambda handler
    :param event: Shopify webhook order json
    :param context: function context
    """
    end_date = datetime.datetime.now()
    refund_params = {
        'financial_status': 'refunded',
        'status': 'any'
    }
    partial_refund_params = {
        'financial_status': 'partially_refunded',
        'status': 'any'
    }
    start_date = end_date - \
        datetime.timedelta(hours=RETRIEVE_ORDERS_FROM_HOURS)
    shopify_handlers = get_all_shopify_handlers()
    for handler in shopify_handlers:
        channel = handler['config']['channel']
        LOGGER.info(f'Processing refunds for channel {channel}')
        handler = handler['handler']
        last_shopify_refunds = handler.get_orders(
            starts_at=start_date.strftime('%Y-%m-%dT%H:%M:00Z'),
            ends_at=end_date.strftime('%Y-%m-%dT%H:%M:00Z'),
            query=refund_params,
            params='refunds'
        )
        last_shopify_refunds += handler.get_orders(
            starts_at=start_date.strftime('%Y-%m-%dT%H:%M:00Z'),
            ends_at=end_date.strftime('%Y-%m-%dT%H:%M:00Z'),
            query=partial_refund_params,
            params='refunds'
        )
        LOGGER.info('Found %s to process since %s hour(s) ago', len(
            last_shopify_refunds), RETRIEVE_ORDERS_FROM_HOURS)
        for refunds in last_shopify_refunds:
            for refund in refunds.get('refunds', []):
                LOGGER.info('Processing refund: %s', json.dumps(refund))
                try:
                    response = _drop_to_queue(refund, channel)
                    LOGGER.info(json.dumps(response))
                except Exception:
                    LOGGER.exception('Failed to send refund to process')
    return


def _drop_to_queue(message, channel):
    message['channel'] = channel
    SQS_HANDLER.push_message(message=json.dumps(message))

    
