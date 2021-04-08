# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016 NewStore, Inc. All rights reserved.
import os
import logging
from lambda_utils.config.config_handler import get_env_variables
from shopify_import_products.sync import run

TENANT = os.environ.get('TENANT', 'frankandoak')
STAGE = os.environ.get('STAGE', 'x')
SHOP = os.environ.get('SHOP', 'storefront-catalog-en')
LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)


def handler(event, context):
    '''
    Handler for the lambda to import the products
    '''
    LOGGER.info(f'Event: {event}')
    env_variables = None if not context else get_env_variables(context.function_name)

    run(env_variables)
    ## Since this is a cron job, We will not returning anything.
