from dataclasses import dataclass

@dataclass(frozen=True)
class Locations:
    netsuite_location_id: int
    ff_node_id: str
