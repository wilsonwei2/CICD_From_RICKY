import logging
import os
import requests
import json
from . import Context
from requests import HTTPError
from .exceptions import NewStoreAdapterException

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class NewStoreAdapter(object):
    def __init__(self, tenant, context, username=None, password=None, host=None):
        self.tenant = tenant
        self.context = context
        self.username = username if username else os.environ.get('newstore_username')
        self.password = password if password else os.environ.get('newstore_password')
        self.host = host if host else os.environ.get('newstore_url_api')
        self.auth = None
        self.headers = self.get_headers()
        self.auth_lambda = os.environ.get('newstore_auth_lambda')
        self.use_auth_lambda = os.environ.get('newstore_use_auth_lambda', '0') == '1'
        self.graphql_client = None
        logger.info('Headers to be utilized on calls to NewStore API: %s' % json.dumps(self.headers, indent=4))

    def get_api_auth(self, auth_required=True):

        if not auth_required:
            return None

        self.ctx = Context(url=self.host)
        if self.use_auth_lambda and self.auth_lambda is not None:
            self.ctx.set_auth_lambda(self.auth_lambda)
        else:
            self.ctx.set_user(self.username, self.password)
        return self.ctx.auth

    def get_headers(self):
        function_name = self.context.function_name if self.context else ''
        function_version = self.context.function_version if self.context else ''
        user_agent = f'lambda-name#{function_name}/{function_version} integrator-name#newstore-integrations'
        return {
            'Content-Type': 'application/json',
            'tenant': self.tenant,
            'X-AWS-Request-ID': self.context.aws_request_id if self.context else '',
            'User-Agent': user_agent
        }

    def get_request(self, resource_path, search_json=None, auth_required=True):
        logger.info('GET %s' % resource_path)
        if search_json:
            logger.info('Search params:\n%s' % (json.dumps(search_json, indent=4)))

        response = requests.get(resource_path, headers=self.headers, auth=self.get_api_auth(auth_required), params=search_json)

        try:
            response.raise_for_status()
        except HTTPError as ex:
            logger.exception(ex)
            raise NewStoreAdapterException(response.text if response.text else repr(ex))

        return response

    def post_request(self, resource_path, send_json):
        logger.info('POST %s' % resource_path)
        logger.info('Sending:\n%s' % (json.dumps(send_json, indent=4)))

        response = requests.post(resource_path, headers=self.headers,
                                 auth=self.get_api_auth(), data=json.dumps(send_json, cls=DecimalEncoder))

        try:
            response.raise_for_status()
        except HTTPError as ex:
            logger.exception('Response: %s; \nException: %s' % (response.text, str(ex)))
            raise NewStoreAdapterException(response.text)
        return response

    def put_request(self, resource_path, send_json):
        logger.info('PUT %s' % resource_path)
        logger.info('Sending:\n%s' % (json.dumps(send_json, indent=4)))

        response = requests.put(resource_path, headers=self.headers,
                                 auth=self.get_api_auth(), data=json.dumps(send_json, cls=DecimalEncoder))
        try:
            response.raise_for_status()
        except HTTPError as ex:
            logger.exception('Response: %s; \nException: %s' % (response.text, str(ex)))
            raise NewStoreAdapterException(response.text)

        return response

    def put_request(self, resource_path, send_json):
        logger.info('PUT %s' % resource_path)
        logger.info('Sending:\n%s' % (json.dumps(send_json, indent=4)))

        response = requests.put(resource_path, headers=self.headers,
                                 auth=self.get_api_auth(), data=json.dumps(send_json, cls=DecimalEncoder))

        try:
            response.raise_for_status()
        except HTTPError as ex:
            logger.exception('Response: %s; \nException: %s' % (response.text, str(ex)))
            raise NewStoreAdapterException(response.text)

        return response

    def patch_request(self, resource_path, send_json={}):
        logger.info('PATCH %s' % resource_path)
        if send_json:
            logger.info('Sending:\n%s' % (json.dumps(send_json, indent=4)))

        response = requests.patch(resource_path, headers=self.headers, auth=self.get_api_auth(), json=send_json)

        try:
            response.raise_for_status()
        except HTTPError as ex:
            logger.exception(ex)
            raise NewStoreAdapterException(response.text)

        return response

    def graphql_request(self, query, params={}):
        logger.info(f'GRAPHQL {query}, params: {json.dumps(params, indent=4)}')

        from gql import gql, Client
        from gql.transport.requests import RequestsHTTPTransport

        if self.graphql_client is None:
            transport = RequestsHTTPTransport(
                url=f"https://{self.host}/api/v1/org/data/query",
                use_json=True,
                verify=True,
                headers=self.headers,
                auth=self.get_api_auth()
            )
            self.graphql_client = Client(transport=transport, fetch_schema_from_transport=True)

        query = gql(query)
        result = self.graphql_client.execute(query, variable_values=params)
        return result


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            return int(o)
        return super(DecimalEncoder, self).default(o)
