from cycle_counts.infrastructure.netsuite_client.requests import CountedItems
from cycle_counts.infrastructure.netsuite_client.response import Response


class NetSuiteClientInterface():

    def inventory_count_search(self) -> Response:
        raise NotImplementedError("Inventory Count Search function not implemented!")

    def inventory_count_update(self, transaction_id: str, items: CountedItems) -> Response:
        raise NotImplementedError("Inventory Count Update function not implemented!")
