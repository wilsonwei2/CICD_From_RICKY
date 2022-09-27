import os
from itertools import repeat
from typing import Dict

from shopify_import_order.models.newstore_return import NewStoreReturn, Item


class NewStoreReturnService:
    def __init__(self):
        self.condition_code = int(os.getenv("CONDITION_CODE", "1"))
        self.item_condition = os.getenv("ITEM_CONDITION", "Sellable")

    def create_newstore_return(self, shopify_refund: Dict, returned_from: str) -> NewStoreReturn:
        items = []
        for line_item in shopify_refund['refund_line_items']:
            item = self._create_item(line_item['line_item'])
            items.extend(repeat(item, int(line_item['quantity'])))

        return NewStoreReturn(items=items, returned_from=returned_from, returned_at=shopify_refund['created_at'],
                              is_historical=False)

    def _create_item(self, item: Dict) -> Item:
        return Item(product_id=item['sku'], item_condition=self.item_condition, condition_code=self.condition_code,
                    return_code=None, return_reason=None)
