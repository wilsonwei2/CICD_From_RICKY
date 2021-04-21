import logging

from dacite import from_dict

from cycle_counts.infrastructure.netsuite_client.requests import CountedItems
from cycle_counts.infrastructure.netsuite_client_interface import NetSuiteClientInterface
from cycle_counts.infrastructure.netsuite_client.response import Response, Transaction, InventoryCount

LOGGER = logging.getLogger()


class NetSuiteMockClient(NetSuiteClientInterface):
    def inventory_count_search(self) -> Response:
        resp = {
            "results": {
                "IC0000025": {
                    "internalid": "663476",
                    "date": "11/4/2020",
                    "location": {
                        "name": "Maddy Bourque",
                        "internalid": "5"
                    },
                    "status": {
                        "name": "Open",
                        "internalid": "Open"
                    },
                    "items": [
                        {
                            "name": "A-002-238 : A-002-238-L",
                            "internalid": "1000201022149-01"
                        }
                    ]
                }
            }
        }
        transactions = []
        for key, value in resp["results"].items():
            transactions.append(Transaction(transaction_id=key, search_payload=from_dict(data=value, data_class=InventoryCount)))
        return Response(inventory_count=transactions)

    def inventory_count_update(self, transaction_id: str, items: CountedItems):
        print(transaction_id)
        print(items)
