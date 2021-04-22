from typing import List, Optional, Dict
from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    name: str
    internalid: str

@dataclass(frozen=True)
class Status:
    name: str
    internalid: str


@dataclass(frozen=True)
class Item:
    name: str
    internalid: str


@dataclass(frozen=True)
class InventoryCount:
    internalid: str
    date: str
    location: Location
    status: Status
    items: List[Item]


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    search_payload: Optional[InventoryCount] = None
    update_status: Dict = None


@dataclass(frozen=True)
class Response:
    inventory_count: List[Transaction]
