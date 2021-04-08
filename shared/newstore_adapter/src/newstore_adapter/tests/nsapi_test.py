import newstore_adapter
import requests_mock
import time
import unittest
import urllib

TEST_TENANT = 'testenant'
TEST_STAGE = 't'
TEST_USER = 'test@example.com'
TEST_PASSWORD = '0123456789ABCDEF'
TEST_CLIENT_ID = 'client-123456789'
TEST_CLIENT_SECRET = 'client-secret-0987654321'

class NSAPITestCase(unittest.TestCase):

    def setUp(self):
        self.ctx = newstore_adapter.Context(TEST_TENANT, TEST_STAGE)
        self.ctx.set_user(TEST_USER, TEST_PASSWORD)

    def tearDown(self):
        return

def token_json_callback(request, context):
    context.status_code = 200
    context.headers['Content-Type'] = 'application/json;charset=UTF-8'
    return {
        'access_token': 'SECRETTOKEN1234567890',
        'token_type': 'Bearer',
        'expires_in': 1
    }

def ping_json_callback(request, context):
    context.status_code = 200
    context.headers['Content-Type'] = 'application/json;charset=UTF-8'
    return { 'pong': True }

class TestNSAPISetup(NSAPITestCase):

    def test_init(self):
        with requests_mock.Mocker() as m:
            m.post('https://testenant.t.newstore.net/v0/token', json=token_json_callback)
            m.get('https://testenant.t.newstore.net/v0/ping', json=ping_json_callback)
            self.ctx.set_keys(TEST_CLIENT_ID, TEST_CLIENT_SECRET)
            self.assertEqual(self.ctx.ping(), {'pong': True}, 'incorrect ping response')
            self.assertEqual(len(m.request_history), 1, 'unexpected request count')
            ping_headers = m.request_history[0].headers
            self.assertEqual(ping_headers.get('Host', None), 'testenant.t.newstore.net', 'incorrect host header')
            self.assertEqual(ping_headers.get('Authorization', None), 'Bearer SECRETTOKEN1234567890', 'incorrect authorization')

    def test_auth_keys(self):
        with requests_mock.Mocker() as m:
            m.post('https://testenant.t.newstore.net/v0/token', json=token_json_callback)
            m.get('https://testenant.t.newstore.net/v0/ping', json=ping_json_callback)
            self.ctx.set_keys(TEST_CLIENT_ID, TEST_CLIENT_SECRET)
            self.assertEqual(self.ctx.ping(), {'pong': True}, 'incorrect ping response')
            self.assertEqual(len(m.request_history), 2, 'unexpected request count')
            conditions_met = 0
            for item in m.request_history[0].text.split('&'):
                item = urllib.unquote(item).decode().split('=')
                if item[0] == 'grant_type':
                    self.assertEqual(item[1], 'client_credentials', 'invalid grant type %s' % item[1])
                    conditions_met += 1
                if item[0] == 'client_id':
                    self.assertEqual(item[1], TEST_CLIENT_ID, 'invalid client id')
                    conditions_met += 1
                if item[0] == 'client_secret':
                    self.assertEqual(item[1], TEST_CLIENT_SECRET, 'invalid client secret')
                    conditions_met += 1
            self.assertEqual(conditions_met, 3, 'some conditions not met')
            self.assertEqual(self.ctx.ping(), {'pong': True}, 'incorrect ping response')
            # Check that we cache the token if called again immediately
            self.assertEqual(len(m.request_history), 3, 'unexpected request count')
            time.sleep(1)
            self.assertEqual(self.ctx.ping(), {'pong': True}, 'incorrect ping response')
            # Check that the token is not used from cache after expiry
            self.assertEqual(len(m.request_history), 5, 'unexpected request count')

    def test_api_host(self):
        self.assertEqual(self.ctx.api_host(), 'testenant.t.newstore.net', 'incorrect API host')

    def test_api_url(self):
        self.assertEqual(self.ctx.api_url(), 'https://testenant.t.newstore.net', 'incorrect API URL')

    def test_host_header(self):
        self.assertEqual(self.ctx.auth.add_host(), {'Host':'testenant.t.newstore.net'}, 'incorrect host header')
