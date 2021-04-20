from dataclasses import dataclass
from typing import Optional, List


@dataclass(frozen=True)
class Item:
    product_id: str
    return_reason: Optional[str]
    return_code: Optional[int]
    item_condition: Optional[str]
    condition_code: Optional[int]


@dataclass(frozen=True)
class NewStoreReturn:
    items: List[Item]
    returned_from: str
    returned_at: Optional[str]
    is_historical: bool
