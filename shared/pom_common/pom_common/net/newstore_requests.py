import os
import json
import logging
import requests
from botocore.exceptions import ClientError
from pom_common.auth.token_handler import Token
from pom_common.net.utils import user_agent_for_lambda
from pom_common.net.newstore_graphql import Newstore_graphql

LOGGER = logging.getLogger(__name__)

class NewstoreRequests:

    def __init__(self, context):
        try:
            self.context = context
            self.tenant = os.environ["TENANT"]
            self.stage = os.environ["STAGE"]
            self.token_handler = Token()
            self.graphql_instance = None
        except AttributeError as error:
            raise RuntimeError("Failed to initialize") from error


    def get_headers(self):
        """ Get required headers """
        access_token = self.token_handler.get_token()
        user_agent = user_agent_for_lambda(self.context)
        return {
            "Authorization": f"Bearer {access_token}",
            "x-tenant-id": os.environ.get("TENANT", "boardriders"),
            "User-Agent": user_agent,
        }


    def get_host(self):
        """ Return the Newstore hostname """
        return f"https://{self.tenant}.{self.stage}.newstore.net"


    def get_graphql(self):
        """ Get the GraphQL instance """
        graphql = self.graphql_instance
        if not graphql:
            graphql = Newstore_graphql(self.tenant, self.stage, self.get_headers())
            self.graphql_instance = graphql
        return graphql

    def graphql(self, query, params={}): # pylint: disable=dangerous-default-value
        """ GraphQL request """
        graphql = self.get_graphql()
        response = graphql.query(query, params)
        return response

    def request(self, method, endpoint, data=None):
        """ request to an endpoint. """

        url = self.get_host() + endpoint
        headers = self.get_headers()

        LOGGER.debug(f"post: Sending {data} to {endpoint} using method {method}")
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=data
        )
        LOGGER.debug(f"post: Response {response.status_code} - {response}")

        # maybe return JSON and status code (or response)?
        return response

    def get(self, endpoint):
        """ GET request to an endpoint. """
        return self.request("GET", endpoint)

    def post(self, endpoint, data):
        """ POST request to an endpoint. """
        return self.request("POST", endpoint, data)

    def put(self, endpoint, data):
        """ PUT request to an endpoint. """
        return self.request("PUT", endpoint, data)

    def patch(self, endpoint, data):
        """ PATCH request to an endpoint. """
        return self.request("PATCH", endpoint, data)

    def delete(self, endpoint, data):
        """ DELETE request to an endpoint. """
        return self.request("DELETE", endpoint, data)
