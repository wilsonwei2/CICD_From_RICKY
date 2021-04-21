import time
import os
from datetime import datetime, timedelta
from typing import List

from cycle_counts.infrastructure.ItemIdsStore import ItemIdsStore
from cycle_counts.infrastructure.netsuite_client.requests import ItemCount, CountedItems
from cycle_counts.infrastructure.netsuite_client.response import Transaction
from cycle_counts.models.locations import Locations
from cycle_counts.models.ns_import_count_task import ImportCountTask, EventItem


class NetSuiteNewStoreService:
    def __init__(self, locations: List[Locations], item_ids_store: ItemIdsStore):
        self.locations = locations
        self.item_ids_store = item_ids_store

    def get_store_id(self, location_id: int) -> str:
        for location in self.locations:
            if location.netsuite_location_id == location_id:
                return location.ff_node_id
        return ''

    def create_import_count_task(self, netsuite_search: Transaction) -> ImportCountTask:
        # need to check this value (days) should come from ssm
        due_date = datetime.strptime(netsuite_search.search_payload.date, "%m/%d/%Y") + timedelta(days=30)

        product_ids = []
        ttl = int(time.time() + 24 * 3600 * int(os.environ.get('TTL_DAYS', 30)))
        for item in netsuite_search.search_payload.items:
            sku = self.get_newstore_sku(item.name)
            self.item_ids_store.update_item(newstore_sku=sku, netsuite_internalid=item.internalid, ttl=ttl)
            product_ids.append(sku)

        external_id = netsuite_search.transaction_id
        return ImportCountTask(product_ids=product_ids, external_id=external_id,
                               due_date=due_date.date().isoformat(), stock_location="main")

    def transf_event_to_netsuite_items(self, items: List[EventItem]) -> CountedItems:
        netsuite_items = []
        for item in items:
            internal_id = self.item_ids_store.get_item({'newstore_sku': item.product_id})
            netsuite_items.append(ItemCount(
                internalid=internal_id.get('netsuite_id'),
                count=item.count
            ))
        return CountedItems(items=netsuite_items)

    def get_newstore_sku(self, netsuite_item_name: str) -> str:
        split_name = netsuite_item_name.split(':')
        if len(split_name) == 2:
            return split_name[1].strip()
        return split_name[0].strip()
