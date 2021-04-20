# Copyright (C) 2016 NewStore Inc, all rights reserved.


"""
Central NewStore adapter library.
The Context class is used to keep state for the current newstore environment target.

Copyright (C) 2017 NewStore, Inc. All rights reserved.
"""

import re
import os
import time
import requests
from . import auth


NEWSTORE_BUCKET_REGEXP = re.compile(os.getenv('NEWSTORE_BUCKET_REGEXP', r'(.*)-(\w)-(\d+)-newstore-dmz'))
NEWSTORE_API_VERSION = os.getenv('NEWSTORE_API_VERSION', 'v0')
NEWSTORE_HQ_VERSION = os.getenv('NEWSTORE_HQ_VERSION', '_/v0')

NEWSTORE_USERNAME = os.getenv('NEWSTORE_USERNAME')
NEWSTORE_PASSWORD = auth.decrypt_env('NEWSTORE_PASSWORD_ENCRYPTED', os.getenv('NEWSTORE_PASSWORD'))


class Context(object):

    '''
    NewStore API Context
    '''

    def __init__(self, tenant=None, stage=None, url=None, function_name=None, function_version=None, aws_request_id=None):
        self.tenant = tenant
        self.stage = stage
        self.url = url
        self.auth = None
        self.deadline = None
        self.function_version = function_version
        self.function_name = function_name
        self.aws_request_id = aws_request_id

    @classmethod
    def for_bucket(cls, bucket_name):
        """ Create a Context by parsing the DMZ bucket name. """
        match = NEWSTORE_BUCKET_REGEXP.match(bucket_name)
        if match is None:
            raise ValueError('invalid bucket name: {}'.format(bucket_name))

        result = Context(tenant=match.group(1), stage=match.group(2))
        if (NEWSTORE_USERNAME is not None) and (NEWSTORE_PASSWORD is not None):
            result.set_user(NEWSTORE_USERNAME, NEWSTORE_PASSWORD)
        return result

    def api_host(self):
        """ Return host name to use for API connections. """
        if self.url is not None:
            return self.url
        elif self.stage == 'l':
            return '%s.l.newstore.local' % self.tenant
        else:
            return '%s.%s.newstore.net' % (self.tenant, self.stage)

    def api_url(self, *args):
        '''
        Compute a URL to access NewStore API.
        Without any additional arguments, the base URL is returned.
        Given one or more arguments, they will be concatenated like this:
            BASE/v0/<arg1>[/arg2 ...]
        To get the import API URL to errors for a given import job 1234:
            api_url('d/import', )
        '''
        if self.stage == 'l':
            result = 'http://localhost:8082'
        else:
            result = 'https://%s' % self.api_host()
        if len(args) > 0:
            parts = [self.api_url(), NEWSTORE_API_VERSION] + [str(x) for x in args]
            result = '/'.join(parts)
        return result

    def api_url_v2(self, *args):
        '''
        Compute a URL to access NewStore API.
        Without any additional arguments, the base URL is returned.
        Given one or more arguments, they will be concatenated like this:
            BASE/v0/<arg1>[/arg2 ...]
        To get the import API URL to errors for a given import job 1234:
            api_url('d/import', )
        '''

        if self.stage == 'l':
            result = 'http://%s:8082' % self.api_host()
        else:
            result = 'https://%s' % self.api_host()
        if len(args) > 0:
            parts = [self.api_url_v2()] + [str(x) for x in args]
            result = '/'.join(parts)
        return result

    def hq_url(self, *args):
        '''
                Compute a URL to access NewStore API.
                Without any additional arguments, the base URL is returned.
                Given one or more arguments, they will be concatenated like this:
                    BASE/v0/<arg1>[/arg2 ...]
                To get the import API URL to errors for a given import job 1234:
                    api_url('d/import', )
                '''
        if self.stage == 'l':
            result = 'http://localhost:8082'
        else:
            result = 'https://%s' % self.api_host()
        if len(args) > 0:
            parts = [self.hq_url(), NEWSTORE_HQ_VERSION] + [str(x) for x in args]
            result = '/'.join(parts)
        return result

    def ping(self):
        """ Send ping request to verify connection. """
        response = requests.get(self.api_url('ping'), auth=self.auth)
        response.raise_for_status()
        return response.json()

    def get_remaining(self):
        """ Remaining seconds for the current execution. """
        remaining = self.deadline - time.time()
        if remaining > 0:
            return remaining
        else:
            raise ValueError('no time left: {}'.format(remaining))

    def set_remaining(self, seconds=0, millis=0):
        """ Sets a deadline for the current execution. """
        self.deadline = time.time() + seconds + (millis / 1000.0)

    def set_user(self, username, password):
        '''
        Create a Bearer authentication object and configure with user credentials.
        '''
        self.auth = auth.Bearer().with_context(self).with_user(username, password)

    def set_keys(self, client_id, client_secret):
        '''
        Create a Bearer authentication object and configure with client credentials.
        '''
        self.auth = auth.Bearer().with_context(self).with_keys(client_id, client_secret)

    def set_auth_lambda(self, lambda_name):
        '''
        Create a Bearer authentication object and configure with auth lambda.
        '''
        self.auth = auth.Bearer().with_context(self).with_lambda(lambda_name)
