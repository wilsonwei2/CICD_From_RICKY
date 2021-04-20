# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016 NewStore, Inc. All rights reserved.
import logging
from lambda_utils.config.config_handler import get_env_variables
from shopify_import_products.sync import run

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)


def handler(event, context):
    '''
    Handler for the lambda to import the products
    '''
    LOGGER.info(f'Event: {event}')
    env_variables = None if not context else get_env_variables(context.function_name)

    run(env_variables)
