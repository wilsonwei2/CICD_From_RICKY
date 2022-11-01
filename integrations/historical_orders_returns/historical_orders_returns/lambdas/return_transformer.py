import os
import logging
import itertools
from newstore_common.aws import init_root_logger
from historical_orders_returns.utils import Utils

init_root_logger(__name__)
LOGGER = logging.getLogger(__name__)

TENANT = os.environ.get('TENANT', 'frankandoak')

VALID_RETURN_CODES = [2864, 392, 395, 398, 401, 404]


class ReturnTransformer():
    def __init__(self, context):
        self.return_item = None
        self.ns_handler = Utils.get_newstore_conn(context)

    def transform_return_items(self, items):
        return_items = []
        for item in items:
            return_code = int(item["return_code"]) if item["return_code"] and int(
                item["return_code"]) in VALID_RETURN_CODES else 99
            returned_product = {
                "product_id": item["sku"],
                "return_reason": item["reason_comment"] or "historical return",
                "return_code": return_code
            }
            for _ in itertools.repeat(None, item["qtyReturning"]):
                return_items.append(returned_product)
        return return_items

    def get_order(self, external_id):
        gql_response = self.ns_handler.graphql("""
query MyQuery($externalId: String!) {
    orders(first: 1, filter: {externalId: {equalTo: $externalId}}) {
        edges {
            node {
                id
            }
        }
    }
}
        """, {
            "externalId": external_id
        })

        if len(gql_response["orders"]["edges"]) == 0:
            raise ValueError(f"Cannot find order {external_id}")
        return gql_response["orders"]["edges"][0]["node"]

    def format_date(self, datestr):
        return f"{datestr.replace(' ', 'T')}.000Z"

    def transform_return(self, return_item):
        gql_order = self.get_order(return_item["order_increment_id"])

        return_request = {
            "is_historical": True,
            "returned_at": self.format_date(return_item["date_requested"]),
            "returned_from": "MTLDC1",
            "items": self.transform_return_items(return_item["items"])
        }

        ns_return = {
            "rma_id": return_item["rma_id"],
            "order_id": gql_order["id"],
            "return": return_request
        }

        LOGGER.info(ns_return)

        return ns_return
