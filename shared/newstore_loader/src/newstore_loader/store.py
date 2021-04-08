# Copyright (C) 2017 NewStore Inc, all rights reserved.

"""
Stores bootstrap.

Copyright (C) 2017 NewStore, Inc. All rights reserved.
"""
import logging
from newstore_loader import config
from newstore_loader import json_stream
from newstore_adapter import bootstrap

LOGGER = logging.getLogger(__name__)

VALID_KEYS = set((
    "active_status", "business_hours", "delivery_zip_codes", "display_price_unit_type",
    "division_name", "gift_wrapping", "image_url", "label", "manager_id",
    "next_day_delivery_postcodes_mapping", "physical_address", "shipping_address",
    "shipping_provider_info", "store_id", "supported_shipping_methods", "tax_id", "tax_included", "timezone",
    "queue_prioritization", "phone_number"
))


def set_store_manager(cfg, store_id, manager_id):
    store_data = bootstrap.get_store(cfg.ctx, store_id)
    store_data["store_id"] = store_id
    store_data["manager_id"] = manager_id
    upsert_store(cfg, store_data)


def upsert_store(cfg, store_data):
    """
    Insert or update store, using bootstrap API's.
    """
    bootstrap.upsert_store(cfg.ctx, store_data['store_id'], store_data)
    LOGGER.info("Created/Updated store %s: %s", store_data['store_id'], store_data['label'])


if __name__ == "__main__":
    import os
    import sys

    cfg = config.Config()

    def add_store(store_data):
        upsert_store(cfg, store_data)

    if len(sys.argv) > 1:
        for filename in sys.argv[1::]:
            read = cfg.read_file
            if os.path.isfile(filename):
                read = json_stream.read_json
            for store in read(filename):
                if isinstance(store, list):
                    for s in store:
                        add_store(s)
                else:
                    add_store(store)
