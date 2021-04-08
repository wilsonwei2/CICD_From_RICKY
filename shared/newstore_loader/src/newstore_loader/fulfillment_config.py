# Copyright (C) 2017 NewStore Inc, all rights reserved.

"""
Employee bootstrap.

Copyright (C) 2017 NewStore, Inc. All rights reserved.
"""

import json
import logging
import os
from newstore_adapter import bootstrap
from newstore_loader import config, json_stream
from newstore_loader.store import set_store_manager

LOGGER = logging.getLogger(__name__)


def process_fulfillment_config(cfg, filename):
    """
    Process one file with person records.
    """
    read = cfg.read_file
    if os.path.isfile(filename):
        read = json_stream.read_json
    for ff_config in read(filename):
        bootstrap.upsert_fulfillment_config(cfg.ctx, ff_config)
        LOGGER.info(' Upserted fulfillment configuration')

if __name__ == '__main__':
    config.main_function(process_fulfillment_config)
