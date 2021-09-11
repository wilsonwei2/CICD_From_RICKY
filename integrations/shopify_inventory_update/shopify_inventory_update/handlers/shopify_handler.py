import logging
import asyncio
import json
import os
import aiohttp
import base64

LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOG_LEVEL)
MAX_ATTEMPTS = int(os.environ.get('MAX_ATTEMPTS', '5') or '5')

SHOPIFY_HOST = 'myshopify.com/admin/'


class ShopifyConnector:
    def __init__(self, api_key, password, shop, url=None, host=SHOPIFY_HOST):
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

    async def update_inventory_quantity_graphql(self, variant_list: list, location_id: int, attempts=0):
        attempts += 1
        LOGGER.info(f'Updating variants:\n{json.dumps(variant_list)}, attempt: {attempts}')
        url_inventory = '{url}api/graphql.json'.format(
            url=self.url)
        if len(variant_list) > 100:
            LOGGER.warning(
                'Inventory GraphQL bulk update cannot process more than 100 items at a time')
            raise Exception(
                'Too much items to process, limit update to 100 for each call')

        mutation = """
        mutation inventoryBulkAdjustQuantityAtLocation($inventoryItemAdjustments: [InventoryAdjustItemInput!]!, $locationId: ID!) {
            inventoryBulkAdjustQuantityAtLocation(inventoryItemAdjustments: $inventoryItemAdjustments, locationId: $locationId) {
                userErrors {
                    field
                    message
                }
                inventoryLevels {
                    available
                        item {
                            id
                        }
                    }
                }
            }
        """
        query = {
            "inventoryItemAdjustments": [
                {
                    "inventoryItemId": f'gid://shopify/InventoryItem/{variant["inventory_item_id"]}',
                    "availableDelta": int(variant['delta'])
                } for variant in variant_list if 'delta' in variant and variant['delta'] != 0
            ],
            "locationId": f'gid://shopify/Location/{location_id}'
        }
        LOGGER.debug(f'Calling {url_inventory} with payload {query}')
        if len(query['inventoryItemAdjustments']) > 0:
            async with aiohttp.ClientSession() as session:
                async with await session.post(url=url_inventory, headers=self.auth_header, json={'query': mutation, 'variables': query}) as response:
                    response_body = await response.json()
                    if response.status == 429:
                        LOGGER.warning('update_inventory_quantity_graphql - Shopify shop api limit reached')
                        if attempts <= MAX_ATTEMPTS:
                            asyncio.sleep(2)
                            return await self.update_inventory_quantity_graphql(variant_list, location_id, attempts)
                        else:
                            raise Exception('update_inventory_quantity_graphql - Shopify shop api limit reached')

                    if len(response_body.get('errors', [])) > 0:
                        for error in response_body['errors']:
                            if error['message'] == 'Throttled':
                                LOGGER.warning(f'update_inventory_quantity_graphql - Shopify shop api limit reached - Attempts: {attempts}')
                                if attempts <= MAX_ATTEMPTS:
                                    asyncio.sleep(2)
                                    return await self.update_inventory_quantity_graphql(variant_list, location_id, attempts)
                                raise Exception('update_inventory_quantity_graphql - Shopify shop api limit reached')

                    response.raise_for_status()

                    if len(response_body.get('data', {}).get('inventoryBulkAdjustQuantityAtLocation', {}).get('userErrors', [])) > 0:
                        errors = response_body['data']['inventoryBulkAdjustQuantityAtLocation']['userErrors']
                        LOGGER.warning(f'Error processing bulk update: {json.dumps(errors)}')
                        raise Exception(errors)
                    LOGGER.debug(f'Updated variants with {json.dumps(response_body)}')
                    return response_body.get('data', {}).get('inventoryBulkAdjustQuantityAtLocation', {}).get('inventoryLevels', [])
        else:
            LOGGER.info('No deltas to process, rejecting this inventory update..')
            return []

    async def get_inventory_quantity(self, variant_list: list, location_id: int, attempts=0):
        attempts += 1
        LOGGER.debug(f'Getting variants inventory levels from Shopify for variant_list: {variant_list}')
        url_inventory = '{url}api/graphql.json'.format(
            url=self.url)
        if len(variant_list) > 100:
            LOGGER.warning(
                'Inventory GraphQL bulk update cannot process more than 100 items at a time')
            raise Exception(
                'Too much items to process, limit update to 100 for each call')

        mutation = """
        mutation inventoryBulkAdjustQuantityAtLocation($inventoryItemAdjustments: [InventoryAdjustItemInput!]!, $locationId: ID!) {
            inventoryBulkAdjustQuantityAtLocation(inventoryItemAdjustments: $inventoryItemAdjustments, locationId: $locationId) {
                userErrors {
                    field
                    message
                }
                inventoryLevels {
                    available
                        item {
                            id
                        }
                    }
                }
            }
        """
        query = {
            "inventoryItemAdjustments": [
                {
                    "inventoryItemId": f'gid://shopify/InventoryItem/{variant["inventory_item_id"]}',
                    "availableDelta": 0
                } for variant in variant_list
            ],
            "locationId": f'gid://shopify/Location/{location_id}'
        }
        LOGGER.info(f'Calling {url_inventory}')
        LOGGER.debug(f'Calling {url_inventory} with payload: \n{query}')
        dummy_jar = aiohttp.DummyCookieJar()
        async with aiohttp.ClientSession(cookie_jar=dummy_jar) as session:
            async with await session.post(url=url_inventory, headers=self.auth_header, json={'query': mutation, 'variables': query}) as response:
                response_body = await response.json()
                if response.status == 429:
                    LOGGER.warning(f'get_inventory_quantity - Shopify shop api limit reached - Attempts: {attempts}')
                    if attempts <= MAX_ATTEMPTS:
                        asyncio.sleep(2)
                        return await self.get_inventory_quantity(variant_list, location_id, attempts)
                    raise Exception('get_inventory_quantity - Shopify shop api limit reached')
                response.raise_for_status()
                LOGGER.debug(f'Response - get_inventory_quantity: {response_body}')

                if len(response_body.get('errors', [])) > 0:
                    for error in response_body['errors']:
                        if error['message'] == 'Throttled':
                            LOGGER.warning(f'get_inventory_quantity - Shopify shop api limit reached - Attempts: {attempts}')
                            if attempts <= MAX_ATTEMPTS:
                                asyncio.sleep(2)
                                return await self.get_inventory_quantity(variant_list, location_id, attempts)
                            raise Exception('get_inventory_quantity - Shopify shop api limit reached')

                if len(response_body.get('data', {}).get('inventoryBulkAdjustQuantityAtLocation', {}).get('userErrors', [])) > 0:
                    errors = response_body['data']['inventoryBulkAdjustQuantityAtLocation']['userErrors']
                    LOGGER.warning(f'Error processing bulk update: {json.dumps(errors)}')
                    # Limit number of retries
                    if attempts <= MAX_ATTEMPTS:
                        LOGGER.info(f'Remove variants or Setting Inventory. Attempts: {attempts}')
                        try:
                            indexes = [int(error['field'][1]) for error in errors]
                            indexes.reverse()
                            error_index = len(indexes) -1
                        except:
                            LOGGER.warning('Failed to handle errors aborting.')
                            return None

                        for idx in indexes:
                            LOGGER.info(f'errors[error_index]: {errors[error_index]}')
                            if errors[error_index]["message"].startswith(
                                    'Quantity couldn\'t be adjusted because this product isn\'t stocked at'):
                                LOGGER.info('The product is not stocked and hence setting inventory')
                                try:
                                    await self.set_inventory_level(variant_list[idx]["inventory_item_id"], location_id, session)
                                except Exception as error:
                                    variant_removed = variant_list.pop(idx)
                                    LOGGER.info(f'Exception thrown: {error} - Removed variant at index: {idx} value: {variant_removed}')
                            else:
                                variant_removed = variant_list.pop(idx)
                                LOGGER.info(f'Removed variant at index: {idx} value: {variant_removed}')
                            error_index = error_index-1
                        asyncio.sleep(2)
                        return await self.get_inventory_quantity(variant_list, location_id, attempts)
                    else:
                        LOGGER.warning('Too many attempts to get/set inventory levels at Shopify.')
                        raise Exception(errors)

                LOGGER.debug(f'Inventory variants list with: \n{response_body}')
                return response_body.get('data', {}).get('inventoryBulkAdjustQuantityAtLocation', {}).get('inventoryLevels', [])

    async def get_locations(self, session):
        """
        Get shopify list of products filtered to only show the variants
        Arguments:
            page {int} -- Page number to get describition from
            session {[aiohttp.ClientSession]} -- AioHttp client session to use in request
        Returns:
            list -- The response list from shopify containing the variants
        """
        LOGGER.info(f'Get locations')

        url = '{url}locations.json'.format(
            url=self.url)

        LOGGER.info(f'Calling {url}')

        async with await session.get(url=url, headers=self.auth_header, params={"active": "true"}) as response:
            used, maximum = _get_rate_limits(response)
            if used and maximum:
                session.update_threshold(used, maximum)
            response.raise_for_status()
            locations_response = []
            locations_response += (await response.json()).get('locations', [])

            LOGGER.debug(f'Returned locations: \n{json.dumps(locations_response, indent=4)}')

            return locations_response

    async def set_inventory_level(self, inv_item_id, location_id, session, atp=0):
        LOGGER.info(f'Setting inventory ATP 0 for inventory_item_id {inv_item_id} and location_id {location_id}')

        url_inventory = f'{self.url}inventory_levels/set.json'

        inventory_data = {
            'inventory_item_id': int(inv_item_id),
            'location_id': int(location_id),
            'available': atp
        }

        LOGGER.debug(f'Calling {url_inventory} with payload {json.dumps(inventory_data)}')

        async with await session.post(url=url_inventory, headers=self.auth_header, json=inventory_data) as response:
            response_body = await response.json()
            if response.status == 429:
                LOGGER.warning('set_inventory_level - Shopify shop api limit reached')
                return await asyncio.ensure_future(
                    self.set_inventory_level(inv_item_id, location_id, session))
            if 'errors' in response_body:
                raise Exception(response_body['errors'][0])
            response.raise_for_status()
            LOGGER.info(f'Response - set_inventory_level: {json.dumps(response_body)}')
            return response_body

def _get_rate_limits(response):
    try:
        thresholds = response.headers.get(
            'HTTP_X_SHOPIFY_SHOP_API_CALL_LIMIT')
        if thresholds:
            thresholds = thresholds.split('/')
            return int(thresholds[0]), int(thresholds[1])
        else:
            return None, None
    except Exception:
        LOGGER.exception(f'Failed to get rate limits: {str(response)}')
        return None, None


def _get_percentage_rate(used, maximum):
    return (float(used) / float(maximum)) * 100.0
