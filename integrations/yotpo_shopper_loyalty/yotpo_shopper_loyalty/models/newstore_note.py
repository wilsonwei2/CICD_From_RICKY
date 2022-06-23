from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class NewStoreNote:
    tags: List[str]
    created_at: str
    id: str # pylint: disable=invalid-name
    order_id: str
    source: str
    text: str
    updated_at: str
