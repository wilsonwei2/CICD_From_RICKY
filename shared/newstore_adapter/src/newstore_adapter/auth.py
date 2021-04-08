# Copyright (C) 2016 NewStore Inc, all rights reserved.

"""
Authentication functions and classes.

Copyright (C) 2017 NewStore, Inc. All rights reserved.
"""

import os
import time
import requests


AUTH_CACHE = None

class Bearer(requests.auth.AuthBase):

    """
    Bearer implements the client side of Oauth2 bearer authentication.
    """

    def __init__(self):
        self.credentials = None
        self.hostname = None
        self.url = None

    def __call__(self, r):
        self.add_host(r.headers)['Authorization'] = self.api_auth()
        return r

    def add_host(self, headers=None):
        """ Add host header. """
        if headers is None:
            headers = {}
        if self.hostname is not None:
            headers['Host'] = self.hostname
        return headers

    def with_context(self, ctx):
        """ Set defaults from `ctx` """
        self.hostname = ctx.api_host()
        self.url = ctx.api_url('token')
        return self

    def with_keys(self, client_id, client_secret):
        """ Initialize credentials from keys. """
        self.credentials = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret
        }
        return self

    def with_user(self, username, password):
        """ Initialize credentials username and password. """
        self.credentials = {
            'grant_type': 'password',
            'username': username,
            'password': password
        }
        return self

    def api_auth(self):
        """ Perform authentication if necessary. """
        global AUTH_CACHE
        result = None
        now = time.time()
        if AUTH_CACHE is not None:
            old = AUTH_CACHE
            if old.get('expires_at', 0) > now:
                result = old

        if result is None:
            response = requests.post(self.url, headers=self.add_host(), data=self.credentials)
            response.raise_for_status()
            result = response.json()
            expires_in = result.get('expires_in', None)
            if isinstance(expires_in, int):
                result['expires_at'] = now + expires_in
                AUTH_CACHE = result

        if result is not None and 'access_token' in result:
            return str('Bearer %s' % result['access_token'])


def decrypt_env(name, fallback=None):
    """ Decrypt environment variable `name` if it exists, or return the given `fallback`. """
    text = os.environ.get(name)
    if text is None:
        return fallback
    import boto3
    from base64 import b64decode
    return boto3.client('kms').decrypt(CiphertextBlob=b64decode(text))['Plaintext']
