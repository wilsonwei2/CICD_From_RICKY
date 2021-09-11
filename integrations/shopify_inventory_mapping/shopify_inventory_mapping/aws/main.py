# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016 NewStore, Inc. All rights reserved.
import logging
from shopify_inventory_mapping.sync import run

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)


def handler(event, _):
    '''
    Handler for the lambda to get the inventory mapping
    '''
    LOGGER.info(f'Event: {event}')

    run()
