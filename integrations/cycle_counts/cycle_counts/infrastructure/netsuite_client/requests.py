from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ItemCount:
    # name: str
    internalid: str
    count: int


@dataclass(frozen=True)
class CountedItems:
    items: List[ItemCount]
