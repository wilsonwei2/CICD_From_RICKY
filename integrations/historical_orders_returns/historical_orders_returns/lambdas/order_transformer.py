import logging
import itertools
from newstore_common.aws import init_root_logger

init_root_logger(__name__)
LOGGER = logging.getLogger(__name__)


class OrderTransformer():
    def __init__(self):
        self.order = None
        self.taxation = None


    def format_date(self, date):
        return date.replace(" ", "")

    def get_order_total(self):
        items = self.order["items"]
        order_total = 0

        for item in items:
            original_price = float(item["Lineitem compare at price"]) if "Lineitem compare at price" in item else 0
            price = float(item["Lineitem price"])
            quantity = int(float(item["Lineitem quantity"]))
            unit_price = float("{:.2f}".format((original_price if original_price > price else price) / quantity))
            unit_discount = 0

            for _ in range(quantity):
                if original_price > price:
                    discount = original_price - price
                    unit_discount = float("{:.2f}".format(discount / quantity))

                adjusted_item_price = unit_price - unit_discount
                order_total = order_total + adjusted_item_price

        return order_total

    def transform_order_address(self, prefix):
        return {
            "first_name": self.order["details"][f"{prefix} First Name"] or "",
            "last_name": self.order["details"][f"{prefix} Last Name"] or "",
            "address_line_1": self.order["details"][f"{prefix} Address1"] or "",
            "city": self.order["details"][f"{prefix} City"] or "",
            "state": self.order["details"][f"{prefix} Province Code"] or "",
            "zip_code": self.order["details"][f"{prefix} Zip"] or "",
            "country": self.order["details"][f"{prefix} Country Code"] or ""
        }


    def transform_payments(self):
        return [{
            "processor": "adyen_historical",
            "correlation_ref": "correlation_ref",
            "type": "captured",
            "amount": float(self.order["payment"]["Transaction Amount"]),
            "method": "historical_payment",
            "processed_at": self.format_date(self.order["payment"]["Transaction Processed At"])
        }]


    def transform_items(self):
        items = self.order["items"]
        ns_items = []
        item_index = 0
        order_discount = float(self.order["details"].get("Discount Amount", "0"))

        for item in items:
            original_price = float(item["Lineitem compare at price"]) if "Lineitem compare at price" in item else 0
            price = float(item["Lineitem price"])
            quantity = int(float(item["Lineitem quantity"]))
            unit_price = float("{:.2f}".format((original_price if original_price > price else price) / quantity))
            unit_discount = 0

            for _ in range(quantity):
                ns_item = {
                    "external_item_id": item["Lineitem sku"],
                    "product_id": item["Lineitem sku"],
                    "price": {
                        "item_price": unit_price,
                        "item_list_price": unit_price,
                        "item_tax_lines": self.transform_item_tax(item)
                    }
                }

                if original_price > price:
                    discount = original_price - price
                    unit_discount = float("{:.2f}".format(discount / quantity))
                    ns_item["price"]["item_discount_info"] = [{
                        "discount_ref": "DISCOUNT",
                        "description": "DISCOUNT",
                        "coupon_code": "DISCOUNT",
                        "type": "fixed",
                        "original_value": unit_discount,
                        "price_adjustment": unit_discount
                    }]

                if order_discount > 0:
                    order_discount_code = self.order.get("Discount Code", "ORDER DISCOUNT")
                    adjusted_item_price = unit_price - unit_discount
                    order_total = self.get_order_total()
                    order_unit_discount = round(adjusted_item_price / order_total * order_discount, 2)
                    ns_item["price"]["item_order_discount_info"] = [{
                        "discount_ref": order_discount_code,
                        "description": order_discount_code,
                        "coupon_code": order_discount_code,
                        "type": "fixed",
                        "original_value": order_discount,
                        "price_adjustment": order_unit_discount
                    }]


                ns_items.append(ns_item)
                item_index += 1

        return ns_items


    def transform_item_tax(self, item):
        tax_lines = []

        for i in itertools.count(start=1):
            # go through all numbered tax lines in the item, break loop if max was reached
            if f"Tax {i} Price" not in item:
                break

            tax_price = float(item[f"Tax {i} Price"])
            quantity = int(float(item["Lineitem quantity"]))

            tax_lines.append({
                "amount": float("{:.2f}".format(tax_price / quantity)),
                "rate": float(item[f"Tax {i} Rate"]),
                "name": item[f"Tax {i} Title"],
                "country_code": self.order["details"]["Billing Country Code"] or ""
            })

        return tax_lines


    def transform_shipping_option(self):
        is_store_order = "Billing Company" in self.order["details"] and len(self.order["details"]["Billing Company"]) > 0

        shipping_option = {
            "price": float(self.order["shipping"]["Shipping Line Price"]),
            "tax": float(self.order["shipping"]["Shipping Tax 1 Price"]) if "Shipping Tax 1 Price" in self.order["shipping"] else 0,
            "service_level_identifier": "IN_STORE_HANDOVER" if is_store_order else "traditional_carrier",
            "shipping_type": "in_store_handover" if is_store_order else "traditional_carrier",
            "display_name": "In Store" if is_store_order else "Standard delivery",
            "fulfillment_node_id": self.order["details"]["Billing Company"] if is_store_order else "MTLDC1",
            "shipping_carrier": "historical_carrier" if is_store_order else "traditional_carrier",
            "zip_code": self.order["details"]["Shipping Zip"] or "",
            "country_code": self.order["details"]["Shipping Country Code"] or ""
        }

        if is_store_order:
            shipping_option["store_id"] = self.order["details"]["Billing Company"]
        else:
            shipping_option["routing_strategy"] = {"strategy": "default"}

        return shipping_option


    def get_taxation(self):
        tax_included = self.order["details"]["Taxes Included"]
        return "tax_excluded" if tax_included == "FALSE" else "tax_included"


    def transform_order(self, order):
        LOGGER.info(f'Start transforming order {order["details"]["Name"]}')

        self.order = order
        self.taxation = self.get_taxation()

        is_store_order = "Billing Company" in self.order["details"] and len(self.order["details"]["Billing Company"]) > 0

        shipments = [{
            "items": self.transform_items(),
            "historical_shipping_option": self.transform_shipping_option()
        }]

        ns_order = {
            "external_id": self.order["details"]["Name"],
            "shop": "storefront-catalog-en",
            "store_id": self.order["details"]["Billing Company"] if is_store_order else "",
            "channel_type": "store" if is_store_order else "web",
            "channel_name": "magento",
            "placed_at": self.format_date(self.order["details"]["Processed At"]),
            "currency": self.order["details"]["Currency"],
            "customer_name": self.order["details"]["Shipping Name"],
            "customer_email": self.order["details"]["Email"] or "",
            "shop_locale": "en-US",
            "customer_language": "en",
            "external_customer_id": self.order["details"]["Mage Customer Id"],
            "is_fulfilled": True,
            "is_historical": True,
            "notification_blacklist": [
                "invoice_created",
                "refund_note_created",
                "order_pending",
                "shipment_cancelled",
                "shipment_dispatched",
                "shipment_delayed",
                "order_cancelled",
                "in_store.ready_for_pick_up"
            ],
            "price_method": self.taxation,
            "shipping_address": self.transform_order_address("Shipping"),
            "billing_address": self.transform_order_address("Billing"),
            "payments": self.transform_payments(),
            "shipments": shipments
        }

        return ns_order
