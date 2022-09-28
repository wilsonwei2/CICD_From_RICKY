# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.

# Runs startup processes (expecting to be 'unused')
import netsuite.netsuite_environment_loader  # pylint: disable=W0611

import logging
import os
import asyncio
import json

import netsuite_shipping_status_rejected_items.transformers.retrieve_netsuite_data as retrieve_netsuite_data
from netsuite_shipping_status_rejected_items.utils import Utils

LOG_LEVEL_STR = os.environ.get('LOG_LEVEL', 'INFO')
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_STR.lower() in ['debug'] else logging.INFO
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOG_LEVEL)

TENANT = os.environ['TENANT']
SEARCH_PAGE_SIZE = os.environ['SEARCH_PAGE_SIZE']

NEWSTORE_HANDLER = None
REJECTED_ORDER_SAVED_SEARCH_ID = None


def handler(event, context):
    LOGGER.info(f"Event received: {json.dumps(event, indent=4)}")
    global NEWSTORE_HANDLER  # pylint: disable=W0603
    NEWSTORE_HANDLER = Utils.get_newstore_conn(context)

    global REJECTED_ORDER_SAVED_SEARCH_ID  # pylint: disable=W0603
    netsuite_config = Utils.get_instance().get_netsuite_config()
    REJECTED_ORDER_SAVED_SEARCH_ID = netsuite_config['rejected_order_saved_search_id']

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(sync_rejected_items())
    loop.stop()
    loop.close()


async def sync_rejected_items():
    mapped_data = retrieve_netsuite_data.retrieve_data_from_saved_search(
        saved_search_id=REJECTED_ORDER_SAVED_SEARCH_ID,
        search_page_size=SEARCH_PAGE_SIZE)

    if not mapped_data:
        LOGGER.info('Search returned no items. Nothing to process.')
        return

    retrieve_netsuite_data.process_reject(mapped_data=mapped_data,
                                          ns_handler=NEWSTORE_HANDLER)

    if mapped_data is None:
        LOGGER.info('Rejections update failed. No sales order items to be marked as imported.')
        return

    retrieve_netsuite_data.mark_rejected_orders_imported(mapped_data)
