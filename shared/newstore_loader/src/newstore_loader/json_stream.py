import json
import logging
import sys
import yaml
from functools import partial

LOGGER = logging.getLogger(__name__)

def read_json(filename):
    '''
    Read and yield a stream of JSON objects.
    '''
    decoder = json.JSONDecoder()
    with open(filename) as input:
        remaining = ''
        for chunk in iter(partial(input.read, 8192), ''):
            remaining += chunk
            while remaining:
                # skip leading space
                remaining = remaining.lstrip()
                try:
                    item, skip = decoder.raw_decode(remaining)
                    remaining = remaining[skip:].lstrip()
                    yield item
                except ValueError as e:
                    break # next chunk

if __name__ == "__main__":

    payload = None

    def add_item(payload, item):
        if payload is None:
            payload = item
        elif type(payload) is dict:
            payload = [ payload, item ]
        else:
            payload.append(item)
        return payload

    if len(sys.argv) > 1:
        for filename in sys.argv[1::]:
            for item in read_json(filename):
                payload = add_item(payload, item)
    else:
        LOGGER.error("usage: json_stream <json-input-file> ...")
        LOGGER.error(" reads each input file in order, and dumps them as YAML")

    if payload is not None:
        dump = yaml.safe_dump
        if type(payload) is list:
            dump = yaml.safe_dump_all
        dump(payload, sys.stdout,
            explicit_start=True, explicit_end=True,
            default_flow_style=False, allow_unicode=True)
