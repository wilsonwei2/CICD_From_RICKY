from dataclasses import dataclass
from typing import Union, List, Optional
from decimal import Decimal
from .common_fields import ExtendedAttribute


@dataclass(frozen=True)
class OrderCreatedExchange:
    order_id: str
    return_id: str


@dataclass(frozen=True)
class OrderCreatedAddress:
    first_name: Optional[str]
    last_name: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    zip_code: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    phone: Optional[str]


@dataclass(frozen=True)
class OrderCreatedItemExtendedAttribute:
    name: str
    value: str


@dataclass(frozen=True)
class OrderCreatedItemExternalIdentifiers:
    sku: Optional[str]
    ean13: Optional[str]


@dataclass(frozen=True)
class OrderCreatedItem:
    id: str
    item_type: Optional[str]
    product_id: str
    pricebook_id: Optional[str]
    pricebook_price: Optional[Decimal]
    list_price: Decimal
    item_discounts: Decimal
    order_discounts: Decimal
    tax: Decimal
    quantity: Decimal
    status: Optional[str]
    extended_attributes: Optional[List[ExtendedAttribute]]
    external_identifiers: Optional[OrderCreatedItemExternalIdentifiers]
    shipping_service_level: Optional[str]


@dataclass(frozen=True)
class OrderCreatedPayload:
    id: str
    external_id: str
    created_at: str
    placed_at: str
    associate_id: Optional[str]
    associate_email: Optional[str]
    channel_type: str
    channel: str
    is_exchange: bool
    exchanges: Optional[List[OrderCreatedExchange]]
    customer_email: Optional[str]
    customer_id: Optional[str]
    is_historical: bool
    billing_address: Optional[OrderCreatedAddress]
    shipping_address: Optional[OrderCreatedAddress]
    price_method: str
    subtotal: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    shipping_tax: Decimal
    tax_total: Decimal
    grand_total: Decimal
    currency: str
    tax_strategy: Optional[str]
    tax_exempt: bool
    extended_attributes: Optional[List[ExtendedAttribute]]
    items: List[OrderCreatedItem]


@dataclass(frozen=True)
class OrderCreated:
    tenant: str
    name: str
    published_at: str
    payload: OrderCreatedPayload
