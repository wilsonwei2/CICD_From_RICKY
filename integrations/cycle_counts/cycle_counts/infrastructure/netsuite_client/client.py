import logging
import requests
from dacite import from_dict

from requests_oauthlib import OAuth1
from dataclasses import dataclass, asdict
from typing import Dict

from cycle_counts.infrastructure.netsuite_client.requests import CountedItems
from cycle_counts.infrastructure.netsuite_client_interface import NetSuiteClientInterface
from cycle_counts.infrastructure.netsuite_client.response import Response, Transaction, InventoryCount


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


@dataclass(frozen=True)
class NetSuiteCredentials:
    consumer_key: str
    consumer_secret: str
    token_key: str
    token_secret: str
    account_id: str


class NetSuiteClient(NetSuiteClientInterface):
    def __init__(self, credentials: NetSuiteCredentials, url: str):
        self.credentials = credentials
        self.url = url

    def inventory_count_search(self) -> Response:
        resp = self._request("GET", self.url)
        transactions = []
        for key, value in resp["results"].items():
            transactions.append(Transaction(transaction_id=key, search_payload=from_dict(data=value, data_class=InventoryCount)))
        return Response(inventory_count=transactions)

    def inventory_count_update(self, transaction_id: str, items: CountedItems) -> Response:
        body = {}
        body[transaction_id] = asdict(items)
        resp = self._request("POST", self.url, body)
        transactions = []
        for key, value in resp["results"].items():
            transactions.append(Transaction(transaction_id=key, update_status=value))
        return Response(inventory_count=transactions)

    def _get_auth(self) -> OAuth1:
        return OAuth1(
            client_key=self.credentials.consumer_key,
            client_secret=self.credentials.consumer_secret,
            resource_owner_key=self.credentials.token_key,
            resource_owner_secret=self.credentials.token_secret,
            realm=self.credentials.account_id
        )

    def _request(self, http_method: str, url: str, json_data: Dict = None):
        LOGGER.info(f'{http_method}: {url} -- {json_data}')
        response = requests.request(method=http_method,
                                    url=url,
                                    auth=self._get_auth(),
                                    headers={"Content-Type": "application/json"},
                                    json=json_data)

        LOGGER.info(f'http response: {response.text}')
        return response.json()
