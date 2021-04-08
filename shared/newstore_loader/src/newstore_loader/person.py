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


def process_persons(cfg, filename):
    """
    Process one file with person records.
    """
    read = cfg.read_file
    if os.path.isfile(filename):
        read = json_stream.read_json
    for person in read(filename):
        person_id = str(person['id'])
        store_id = str(person['store_id'])
        if 'email' in person:
            # Skip manager-only entries
            person_request = {
                'id': person_id,
                'first_name': person['first_name'],
                'last_name': person['last_name'],
                'email': person['email'],
                'store_id': store_id,
                'telephone_number': person['telephone_number']
            }
            bootstrap.upsert_employee(cfg.ctx, person_id, person_request)
            LOGGER.info(' Upserted employee: %s: %s %s',
                        person_request['id'],
                        person_request['first_name'],
                        person_request['last_name']
                       )
            if person.get('role', '') == 'Store Manager':
                set_store_manager(cfg, store_id, person_id)

if __name__ == '__main__':
    config.main_function(process_persons)
