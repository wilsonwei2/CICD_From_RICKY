from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class ProviderRatesRequestProductPrice:
    amount: float
    currency: str


@dataclass(frozen=True)
class ProviderRatesRequestProductWeight:
    value: float
    unit: str


@dataclass(frozen=True)
class ProviderRatesRequestProductDimensions:
    length: int
    width: int
    height: int
    unit: str


@dataclass(frozen=True)
class ProviderRatesRequestProduct:
    product_id: str
    quantity: int
    price: ProviderRatesRequestProductPrice
    weight: ProviderRatesRequestProductWeight
    dimensions: ProviderRatesRequestProductDimensions


@dataclass(frozen=True)
class ProviderRatesRequestBag:
    products: List[ProviderRatesRequestProduct]


@dataclass(frozen=True)
class ProviderRatesRequestAddress:
    country_code: str
    zip_code: Optional[str]
    address_line_1: Optional[str]
    city: Optional[str]
    state: Optional[str]
    phone: Optional[str]


@dataclass(frozen=True)
class ProviderRatesRequest:
    request_id: str
    bag: ProviderRatesRequestBag
    shipping_address: ProviderRatesRequestAddress
