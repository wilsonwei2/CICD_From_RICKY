"""
Our sincere gratitude to the author of the following post for providing the basis for this class.
https://community.shopify.com/c/shopify-apis-and-sdks/python-graphql-example-with-rate-limiting-and-error-checking/td-p/713261
"""

import json
import time
import requests
import logging

from yotpo_shopper_loyalty.handlers.utils import Utils

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

class ShopifyDiscountCodeGQL:
    """
    Class to disable Shopify coupons using the
    Shopify GraphQL Admin API.
    """
    def __init__(self) -> None:
        self.api_version = '2022-07'
        self.utils = Utils.get_instance()
        self.param_store = self.utils.get_parameter_store()
        self.shopify_config = self.param_store.get_param('shopify')
        self.api_key = self.shopify_config['username']
        self.password = self.shopify_config['password']
        self.shop = self.shopify_config['shop']
        self.shop_url = f'https://{self.api_key}:{self.password}@{self.shop}.myshopify.com/admin/api/{self.api_version}'

    def disable_shopify_coupon(self, code: str) -> None:
        """
        This is the main calling function that is exposed
        in order to disable a coupon.
        """
        coupon_id = self._get_coupon_id_by_code(code)
        return self._disable_coupon_gql(coupon_id)

    def _get_coupon_id_by_code(self, code: str) -> str:
        """
        Get the coupon ID by code. This coupon ID is required to
        disable a coupon.
        """
        query = f"""
            {{
                codeDiscountNodeByCode(code:"{code}") {{
                    codeDiscount
                    id
                }}
            }}
        """
        LOGGER.info(f'Get coupon GQL query: {query}')
        response = self._call_shopify_gql(query)
        return response['codeDiscountNodeByCode']['id']

    def _disable_coupon_gql(self, coupon_id: str) -> None:
        """
        Disable a coupon using the Shopify GraphQL Admin API.
        A coupon ID is required to disable a coupon.
        """
        mutation = """
        mutation discountCodeDeactivate($id:ID!) {
            discountCodeDeactivate(id: $id) {
                codeDiscountNode {
                codeDiscount {
                    ... on DiscountCodeBasic {
                      title
                      status
                      startsAt
                      endsAt
                    }
                }
            }
                userErrors {
                    field
                    code
                    message
                }
            }
        }
        """
        variables = {"id": coupon_id}
        LOGGER.info(f'Disable coupon GQL query: {mutation}')
        LOGGER.info(f'Disable coupon GQL variables: {variables}')
        response = self._call_shopify_gql(mutation, variables)
        LOGGER.info(f'Disable coupon GQL response: {response}')
        if response['discountCodeDeactivate']['codeDiscountNode']['codeDiscount']['status'] != 'EXPIRED':
            raise ValueError('Coupon not expired')

    def _call_shopify_gql(self, gql_string: str, variables=None):
        """
        This function makes the actual API call, it also handles errors and
        rate limiting.
        """
        response = requests.post(f'{self.shop_url}/graphql.json', json={'query': gql_string, 'variables':variables})
        if response.status_code == 400:
            raise ValueError('GraphQL error:' + response.text)
        answer = json.loads(response.text)
        throttle_status = None
        if 'errors' in answer:
            try:
                throttle_status = answer['errors'][0]['extensions']['code']
            except KeyError:
                pass
            if throttle_status != 'THROTTLED':
                raise ValueError('GraphQL error:' + repr(answer['errors']))
        ql_required = answer['extensions']['cost']['requestedQueryCost']
        ql_limit = answer['extensions']['cost']['throttleStatus']['maximumAvailable']
        ql_avail = answer['extensions']['cost']['throttleStatus']['currentlyAvailable']
        LOGGER.info(f'GraphQL throttling status: {str(ql_avail)}/{str(int(ql_limit))}')
        while throttle_status == 'THROTTLED':
            LOGGER.info(f'Waiting (GraphQL throttling)...{str(ql_avail)}/{str(int(ql_limit))} used, requested {str(ql_required)}')
            time.sleep(1)
            response = requests.post(f'{self.shop_url}/graphql.json', json={'query': gql_string, 'variables':variables})
            answer = json.loads(response.text)
            try:
                throttle_status = answer['errors'][0]['extensions']['code']
            except KeyError:
                throttle_status = None
        return answer['data']
