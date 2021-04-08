# Copyright (C) 2016 NewStore Inc, all rights reserved.

"""
Transformer handoff utility.

Copyright (C) 2017 NewStore, Inc. All rights reserved.
"""

import logging
import json
import os
import re
import sys

if sys.version_info >= (3,0):
    import http.client as httplib
else:
    import httplib

# Constants, overridable from the process environment
LOGGER = logging.getLogger()
TRANSFORMER_HOST = os.getenv('TRANSFORMER_HOST', '{tenant}.{stage}.transformer.dmz.newstore.io')
TRANSFORMER_PATH = os.getenv('TRANSFORMER_PATH', '/transform')
TRANSFORMER_HTTP = re.compile(os.getenv('TRANSFORMER_HTTP', r'\.dmz\.newstore\.io$'))


def post(ctx, job):
    """
    Performs a POST request to the transformer with the given body.

    Keyword arguments:
    ctx -- initialized adapter context
    job -- import job to hand off to transformer
    """

    host = TRANSFORMER_HOST.format(tenant=ctx.tenant, stage=ctx.stage)
    LOGGER.info('transformer request host: %s', host)
    LOGGER.info('transformer request path: %s', TRANSFORMER_PATH)

    data = json.dumps({
        'source_uri': job.source_uri,
        'import_job_id': job.import_id,
        'import_job_type': job.import_type,
        'tenant_name': ctx.tenant,
        'stage': ctx.stage
    })
    LOGGER.info('transformer request body: %s', data)

    connection = None
    try:
        connection = get_connection(host, ctx.get_remaining())
        connection.request('POST', TRANSFORMER_PATH, data, {'Content-Type': 'application/json'})
        result = connection.getresponse()
        return result.read()
    except httplib.HTTPException as e:
        LOGGER.error(e)
        raise e
    finally:
        if connection is not None:
            connection.close()


def get_connection(host, timeout):
    """
    Choose a connection type for connections to host.
    """
    if TRANSFORMER_HTTP.search(host):
        LOGGER.info('transformer request protocol: http')
        return httplib.HTTPConnection(host, timeout=timeout)
    else:
        LOGGER.info('transformer request protocol: https')
        return httplib.HTTPSConnection(host, timeout=timeout)
