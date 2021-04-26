import logging
import asyncio
import json
import os
import aiohttp
import base64

SHOW_DEBUG_LOGS = os.environ.get('SHOW_DEBUG_LOGS', '0').lower()
LOGGER = logging.getLogger(__name__)
if SHOW_DEBUG_LOGS in ('1', 't', 'true', 'yes'):
    LOGGER.setLevel(logging.DEBUG)
else:
    LOGGER.setLevel(logging.INFO)
SHOPIFY_HOST = 'myshopify.com/admin/'


class ShopifyConn:
    def __init__(self, api_key, password, shop, url=None, host=SHOPIFY_HOST): # pylint: disable=R0913
        self.host = host
        self.api_key = api_key
        self.password = password

        auth_string = ('{key}:{pwd}'.format(
            key=self.api_key, pwd=self.password))
        self.auth_header = {
            'Content-Type': 'application/json ',
            'Authorization': 'Basic {auth_base64}'.format(
                auth_base64=base64.b64encode(
                    auth_string.encode()).decode('utf-8')
            )
        }
        self.shop = shop
        if not url:
            self.url = 'https://{shop}.{host}'.format(
                shop=shop, host=host)
        else:
            self.url = url

    async def set_inventory_level(self, inv_item_id, location_id, atp=0):
        LOGGER.info(f'Setting inventory ATP 0 for inventory_item_id {inv_item_id} and location_id {location_id}')

        url_inventory = f'{self.url}inventory_levels/set.json'

        inventory_data = {
            'inventory_item_id': int(inv_item_id),
            'location_id': int(location_id),
            'available': atp
        }

        LOGGER.info(f'Calling {url_inventory} with payload {json.dumps(inventory_data)}')

        async with aiohttp.ClientSession() as session:
            async with await session.post(url=url_inventory, headers=self.auth_header, json=inventory_data) as response:
                response_body = await response.json()
                if response.status == 429:
                    LOGGER.warning('Shopify shop api limit reached')
                    return await asyncio.ensure_future(
                        self.set_inventory_level(inv_item_id, location_id))
                if 'errors' in response_body:
                    raise Exception(response_body['errors'][0])
                response.raise_for_status()
                LOGGER.info(f'Response: {json.dumps(response_body)}')
                return response_body

    async def get_inventory_level(self, inv_item_id, location_id):
        LOGGER.info(f'Getting inventory levels for inventory_item_id {inv_item_id} and location_id {location_id}')

        url_inventory = f'{self.url}inventory_levels.json'

        inventory_data = {
            'inventory_item_ids': int(inv_item_id),
            'location_ids': int(location_id)
        }

        LOGGER.info(f'Calling {url_inventory} with params {json.dumps(inventory_data)}')

        async with aiohttp.ClientSession() as session:
            async with await session.get(url=url_inventory, headers=self.auth_header,
                                         params=inventory_data) as response:
                response_body = await response.json()
                if response.status == 429:
                    LOGGER.warning('Shopify shop api limit reached')
                    return await asyncio.ensure_future(
                        self.get_inventory_level(inv_item_id, location_id))
                response.raise_for_status()
                LOGGER.info(f'Response: {json.dumps(response_body)}')
                return response_body.get('inventory_levels')
