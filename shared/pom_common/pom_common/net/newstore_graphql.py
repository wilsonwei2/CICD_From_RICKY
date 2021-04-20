from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

GRAPHQL_ENDPOINT = "api/v1/org/data/query"

class Newstore_graphql():
    def __init__(self, tenant, stage = "x", headers={}):
        headers = dict({}, **headers)

        transport = RequestsHTTPTransport(
            url=f"https://{tenant}.{stage}.newstore.net/{GRAPHQL_ENDPOINT}",
            use_json=True,
            verify=True,
            headers=headers,
        )
        self.client = Client(transport=transport, fetch_schema_from_transport=True)

    def query(self, query_str, params={}):
        query = gql(query_str)
        result = self.client.execute(query, variable_values=params)
        return result
