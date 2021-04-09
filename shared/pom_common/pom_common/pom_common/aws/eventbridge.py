"""
File: shared/pom_common/pom_common/aws/eventbridge.py
Description: Eventbridge Handler
"""
import os
import logging
import json
from datetime import datetime

import boto3

LOGGER = logging.getLogger(__name__)


def get_event(payload, source, detail_type, eventbus_name):
    """ Format Eventridge Event """
    detail = json.dumps(payload)
    return {
        "Source": source,
        "Time": datetime.utcnow().isoformat(),
        "DetailType": detail_type,
        "Detail": detail,
        "EventBusName": eventbus_name
    }


def put_event(payload, source, detail_type, eventbus_name):
    """ Send event to event bridge bus """
    event = get_event(payload, source, detail_type, eventbus_name)
    client = boto3.client("events")
    # we send one event, if FailedEntryCount is not 0 event request failed
    return client.put_events(Entries=[event])
