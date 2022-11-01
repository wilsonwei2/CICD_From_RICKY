import os
import logging
import requests
from requests import HTTPError
from typing import List

LOGGER = logging.getLogger(__name__)
LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER.setLevel(LOG_LEVEL)


class NShandler():
    host = None
    username = None
    password = None
    token = None
    tenant = None

    def __init__(self, host, username, password, tenant):
        self.host = host
        self.username = username
        self.password = password
        self.tenant = tenant

    def get_token(self):
        if not self.token:
            LOGGER.info(f'Getting token from newstore {self.host}')
            url = f'https://{self.host}/v0/token'
            headers = {
                'Host': self.host
            }
            form = {
                'grant_type': 'password',
                'username': self.username,
                'password': self.password
            }
            response = requests.post(url=url, headers=headers, data=form)
            response.raise_for_status()
            self.token = response.json()
        else:
            LOGGER.info('Token already exists')
        return self.token['access_token']

    def get_headers(self):
        return {
            'Content-Type': 'application/json',
            'tenant': self.get_tenant(),
            'Authorization': f'Bearer {self.get_token()}'
        }

    def get_order_by_external_id(self, ext_id):
        """
        Get Newstore order based on country_code, zip and email,
        country_code can be empty
        """
        url = f'https://{self.host}/v0/d/external_orders/{ext_id}'
        LOGGER.info(f'Getting order values from newstore {url}')
        response = requests.get(url=url, headers=self.get_headers())
        response.raise_for_status()
        return response.json()

    def get_order(self, order_id):
        """
        Get Newstore order
        """
        url = f'https://{self.host}/v0/c/orders/{order_id}'
        LOGGER.info(f'Getting order values from newstore {url}')
        response = requests.patch(url=url, headers=self.get_headers(), json={})
        response.raise_for_status()
        return response.json()

    def fulfill_order(self, order_data):
        url = f'https://{self.host}/v0/d/fulfill_order'
        LOGGER.info(
            f"Sending order {order_data['external_id']} to {url} Payload {order_data}")

        response = requests.post(url, headers=self.get_headers(), json=order_data)
        try:
            response.raise_for_status()
        except HTTPError as ex:
            LOGGER.error(
                f"Response for order {order_data['external_id']} {response.text}; \nException: {str(ex)}",
                exc_info=True)
            raise
        return response.json()

    def get_in_store_pickup_options(self, request_json):
        """ Retrieve in-store pickup offer tokens based on geo location, items and search radius """
        url = f'https://{self.host}/v0/d/in_store_pickup_options'
        response = requests.post(url, headers=self.get_headers(), json=request_json)
        response.raise_for_status()
        return response.json()

    def get_product(self, sku: str) -> dict:
        product_sku = sku.replace("/", "%2F")
        url = f'https://{self.host}/api/v1/shops/storefront-catalog-en/products/{product_sku}'
        query = {
            'locale': 'en-US'
        }
        response = requests.get(url=url, headers=self.get_headers(), params=query)
        response.raise_for_status()
        return response.json()

    def create_return(self, order_id, return_json):
        url = f'https://{self.host}/v0/d/orders/{order_id}/returns'
        LOGGER.info("Create Newstore Return")
        response = requests.post(url, headers=self.get_headers(), json=return_json)
        try:
            response.raise_for_status()
        except HTTPError as ex:
            LOGGER.info(f'Response: {response.text}; \nException: {str(ex)}', exc_info=True)
            if "The following products were already returned" in response.text:
                return {"repeated_returned": True, "message": response.json().get("message")}
            raise
        success_response = response.json()
        LOGGER.info(f"Response {response.text}")
        success_response["repeated_returned"] = False
        return success_response

    def create_order_note(self, order_id: str, text: str, source: str, tags: List[str]):
        url = f'https://{self.host}/v0/d/orders/{order_id}/notes'
        LOGGER.info("Create Order Note")
        note = {}
        note["text"] = text
        note["source"] = source
        note["tags"] = tags
        response = requests.post(url, headers=self.get_headers(), json=note)
        response.raise_for_status()
        return response.json()

    def delete_order_note(self, order_id: str, note_id: str):
        url = f'https://{self.host}/v0/d/orders/{order_id}/notes/{note_id}'
        LOGGER.info("Delete Order Note")
        response = requests.delete(url, headers=self.get_headers())
        response.raise_for_status()

    def get_store(self, store_id):
        url = f'https://{self.host}/v0/i/stores/{store_id}'
        response = requests.get(url=url, headers=self.get_headers())
        response.raise_for_status()
        return response.json()

    def get_host(self):
        return self.host

    def get_tenant(self):
        return self.tenant
