from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class ImportCountTask:
    due_date: str
    product_ids: List[str]
    external_id: str
    stock_location: Optional[str]


@dataclass(frozen=True)
class EventItem:
    product_id: str
    stock_on_hand: int
    count: int


@dataclass(frozen=True)
class NewStoreInventoryCountEvent:
    ns_id: str
    fulfillment_location_id: str
    items: List[EventItem]
