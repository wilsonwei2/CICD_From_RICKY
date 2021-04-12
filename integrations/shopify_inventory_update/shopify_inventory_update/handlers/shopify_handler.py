import logging
import asyncio
import json
import os
import aiohttp
import base64
import random
from time import sleep

SHOW_DEBUG_LOGS = os.environ.get('SHOW_DEBUG_LOGS', '0').lower()

LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

if SHOW_DEBUG_LOGS in ('1', 't', 'true', 'yes'):
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

SHOPIFY_HOST = 'myshopify.com/admin/'
SHOPIFY_MAX_PERCENT_RATE_LIMIT = float(
    os.environ.get('SHOPIFY_MAX_PERCENT_RATE_LIMIT', '85.0'))

percentage_usage = 0.0


class RateLimiter:
    """ Rate limits an HTTP client calls. """

    used = 1
    holding = 0
    maximum = 5
    client = None


    def __init__(self, client):
        self.client = client


    # Intercept call with method PUT
    async def put(self, *args, **kwargs):
        await self.wait_for_slot()
        return self.client.put(*args, **kwargs)


    # Intercept call with method GET    
    async def get(self, *args, **kwargs):
        await self.wait_for_slot()
        return self.client.get(*args, **kwargs)

    
    async def post(self, *args, **kwargs):
        await self.wait_for_slot()
        return self.client.post(*args, **kwargs)

    
    async def wait_for_slot(self):
        global percentage_usage
        self.holding += 1
        while self._validate_available_slots():
            await asyncio.sleep(random.randint(1, 10))
        self.holding -= 1
        percentage_usage = _get_percentage_rate(self.used, self.maximum)
        return


    def _validate_available_slots(self):
        global percentage_usage
        future_percentage_rate = _get_percentage_rate(
            (self.used + 1), self.maximum)
        exp_validate_slot_free = (
            percentage_usage >= SHOPIFY_MAX_PERCENT_RATE_LIMIT)
        if exp_validate_slot_free:
            random_validator = random.randint(1, 10)
            if random_validator == 5:
                self.used += 1
                return False
            return True
        else:
            self.used += 1
            return False


    def update_threshold(self, used, maximum):
        global percentage_usage
        if self.maximum != maximum:
            self.maximum = maximum
        self.used = used
        percentage_usage = _get_percentage_rate(used, maximum)
        logger.info('Update shopify rate - Used shopify rate slot is %s with usage percent in %.2f',
                    f'{self.used}/{self.maximum}', float(percentage_usage))
        return


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

    async def update_variant_quantity(self, variant_id, atp, session):
        logger.info('Updating %s to %s', variant_id, str(atp))
        url_variant = '{url}variants/{id}.json'.format(
            url=self.url, id=variant_id)
        variant_data = {
            'variant': {
                'id': variant_id,
                'inventory_quantity': atp
            }
        }
        logger.debug('Calling %s with payload %s',
                    url_variant, json.dumps(variant_data))

        async with await session.put(url=url_variant, headers=self.auth_header, json=variant_data) as response:
            response_body = await response.json()
            used, maximum = _get_rate_limits(response)
            if used and maximum:
                session.update_threshold(used, maximum)
            if response.status == 429:
                logger.warning('Shopify shop api limit reached')
                return await asyncio.ensure_future(
                    self.update_variant_quantity(variant_id, atp, session))
            response.raise_for_status()
            logger.info('Updated variant %s with %s ',
                        variant_id, json.dumps(response_body))
            return response_body

    async def update_inventory_quantity(self, variant_id, atp, location_id,  session):
        logger.info('Updating %s to %s', variant_id, str(atp))
        url_inventory = '{url}inventory_levels/set.json'.format(
            url=self.url, id=variant_id)
        inventory_data = {
            'inventory_item_id': int(variant_id),
            'available': atp,
            'location_id': int(location_id)
        }
        logger.info('Calling %s with payload %s',
                    url_inventory, json.dumps(inventory_data))

        async with await session.post(url=url_inventory, headers=self.auth_header, json=inventory_data) as response:
            response_body = await response.json()
            used, maximum = _get_rate_limits(response)
            if used and maximum:
                session.update_threshold(used, maximum)
            if response.status == 429:
                logger.warning('Shopify shop api limit reached')
                return await asyncio.ensure_future(
                    self.update_variant_quantity(variant_id, atp, session))
            response.raise_for_status()
            logger.debug('Updated variant %s with %s ',
                        variant_id, json.dumps(response_body))
            return response_body

    async def update_inventory_quantity_graphql(self, variant_list: list, location_id: int):
        logger.info('Updating variants:\n%s', json.dumps(variant_list))
        url_inventory = '{url}api/graphql.json'.format(
            url=self.url)
        if len(variant_list) > 100:
            logger.warning(
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
        logger.debug('Calling %s with payload %s',
                    url_inventory, json.dumps(query))
        if len(query['inventoryItemAdjustments']) > 0:
            async with aiohttp.ClientSession() as session:
                async with await session.post(url=url_inventory, headers=self.auth_header, json={'query': mutation, 'variables': query}) as response:
                    ## THIS COULD BE A BUG LOOK INTO IT
                    variant_id = None
                    atp = 0
                    response_body= await response.json()
                    if response.status == 429:
                        logger.warning('Shopify shop api limit reached')
                        return await asyncio.ensure_future(
                            self.update_variant_quantity(variant_id, atp, session))
                    response.raise_for_status()
                    if len(response_body.get('data', {}).get('inventoryBulkAdjustQuantityAtLocation', {}).get('userErrors', [])) > 0:
                        errors = response_body['data']['inventoryBulkAdjustQuantityAtLocation']['userErrors']
                        logger.warning('Error processing bulk update: %s', json.dumps(errors))
                        raise Exception(errors)
                    logger.debug('Updated variants with %s ', json.dumps(response_body))
                    return response_body.get('data', {}).get('inventoryBulkAdjustQuantityAtLocation', {}).get('inventoryLevels', [])
        else:
            logger.info('No deltas to process, rejecting this inventory update..')
            return []

    async def get_inventory_quantity(self, variant_list: list, location_id: int, attempts=0):
        attempts += 1
        logger.debug(f'Getting variants inventory levels from Shopify for variant_list: {variant_list}')
        url_inventory = '{url}api/graphql.json'.format(
            url=self.url)
        if len(variant_list) > 100:
            logger.warning(
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
        logger.info('Calling %s',
                    url_inventory)
        logger.debug('Calling %s with payload: \n%s',
                    url_inventory, json.dumps(query, indent=4))
        async with aiohttp.ClientSession() as session:
            async with await session.post(url=url_inventory, headers=self.auth_header, json={'query': mutation, 'variables': query}) as response:
                response_body= await response.json()
                ## THIS COULD BE A BUG LOOK INTO IT
                variant_id = None
                atp = 0
                if response.status == 429:
                    logger.warning('Shopify shop api limit reached')
                    return await asyncio.ensure_future(
                        self.update_variant_quantity(variant_id, atp, session))
                response.raise_for_status()
                logger.debug(f'Response: {response}')
                logger.debug(f'Response json await: {response_body}')

                if len(response_body.get('data', {}).get('inventoryBulkAdjustQuantityAtLocation', {}).get('userErrors', [])) > 0:
                    errors = response_body['data']['inventoryBulkAdjustQuantityAtLocation']['userErrors']
                    logger.warning('Error processing bulk update: %s', json.dumps(errors))
                    # Limit number of retries
                    if attempts <= 3:
                        logger.info(f'Remove variants or Setting Inventory. Attempts: {attempts}')
                        indexes = [int(error['field'][1]) for error in errors]
                        indexes.reverse()
                        error_index = len(indexes) -1

                        for idx in indexes:
                            logger.info(f'errors[error_index]: {errors[error_index]}')
                            if errors[error_index]["message"].startswith(
                                    'Quantity couldn\'t be adjusted because this product isn\'t stocked at'):
                                logger.info('The product is not stocked and hence setting inventory')
                                try:
                                    await self.set_inventory_level(variant_list[idx]["inventory_item_id"], location_id)
                                except Exception:
                                    variant_removed = variant_list.pop(idx)
                                    logger.info(f'Removed variant at index: {idx} value: {variant_removed}')
                            else:
                                variant_removed = variant_list.pop(idx)
                                logger.info(f'Removed variant at index: {idx} value: {variant_removed}')
                            error_index = error_index-1
                        return await self.get_inventory_quantity(variant_list, location_id, attempts)
                    else:
                        raise Exception(errors)

                logger.debug('Inventory variants list with: \n%s ', json.dumps(response_body, indent=4))
                return response_body.get('data', {}).get('inventoryBulkAdjustQuantityAtLocation', {}).get('inventoryLevels', [])
  
    async def delta_inventory_quantity(self, inventory_item_id, adjust_value, location_id,  session):
        logger.info('Updating %s to %s', inventory_item_id, str(adjust_value))
        url_inventory= '{url}inventory_levels/adjust.json'.format(
            url=self.url, id=inventory_item_id)
        inventory_data= {
            'inventory_item_id': int(inventory_item_id),
            'available_adjustment': adjust_value,
            'location_id': int(location_id)
        }
        logger.debug('Calling %s with payload %s',
                    url_inventory, json.dumps(inventory_data))

        async with await session.post(url=url_inventory, headers=self.auth_header, json=inventory_data) as response:
            response_body= await response.json()
            used, maximum= _get_rate_limits(response)
            if used and maximum:
                session.update_threshold(used, maximum)
            if response.status == 429:
                logger.warning('Shopify shop api limit reached')
                return await asyncio.ensure_future(
                    self.delta_inventory_quantity(inventory_item_id, adjust_value, location_id,  session))
            response.raise_for_status()
            logger.debug('Updated variant %s with %s ',
                        inventory_item_id, json.dumps(response_body))
            return response_body


    async def get_variants_list(self, session, next_page=None):
        """
        Get shopify list of products filtered to only show the variants
        Arguments:
            page {int} -- Page number to get describition from
            session {[aiohttp.ClientSession]} -- AioHttp client session to use in request
        Returns:
            list -- The response list from shopify containing the variants
            str -- last_page
        """
        SHOPIFY_API_VERSION = os.environ.get('SHOPIFY_API_VERSION', '2020-04')
        if next_page:
            url = next_page
        else:
            url = '{url}api/{SHOPIFY_API_VERSION}/products.json'.format(
                url=self.url, SHOPIFY_API_VERSION= SHOPIFY_API_VERSION)
        query = {
            'fields': 'variants',
            'limit': int(50)
            }

        logger.debug(f'Calling {url} with payload {json.dumps(query)}')

        async with await session.get(url=url, headers=self.auth_header, params=query) as response:
            used, maximum= _get_rate_limits(response)
            if used and maximum:
                session.update_threshold(used, maximum)
            response.raise_for_status()
            links = response.headers.get('Link', '').split(',')
            next_page = ''
            previous_page = ''
            for link in links:
                if link and len(link.split(';')) > 1:
                    cursor_url = link.split(';')[0]
                    rel = link.split(';')[1]
                    if 'previous' in rel:
                        previous_page = cursor_url.strip()[1:-1]
                    elif 'next' in rel:
                        next_page = cursor_url.strip()[1:-1]
            response = await response.json()
            products = response.get('products')
            variants_response = []
            for variant in products:
                variants_response += variant.get('variants')
            return variants_response, previous_page, next_page

    async def get_locations(self, session):
        """
        Get shopify list of products filtered to only show the variants
        Arguments:
            page {int} -- Page number to get describition from
            session {[aiohttp.ClientSession]} -- AioHttp client session to use in request
        Returns:
            list -- The response list from shopify containing the variants
        """
        logger.info(f'Get locations')

        url= '{url}locations.json'.format(
            url=self.url)

        logger.info(f'Calling {url}')

        async with await session.get(url=url, headers=self.auth_header, params={"active": "true"}) as response:
            used, maximum= _get_rate_limits(response)
            if used and maximum:
                session.update_threshold(used, maximum)
            response.raise_for_status()
            locations_response= []
            locations_response += (await response.json()).get('locations', [])

            logger.debug(f'Returned locations: \n{json.dumps(locations_response, indent=4)}')

            return locations_response

    async def get_metafields(self, session, product_id, variant_id, params=None):
        """
        Get shopify list of metafields for a specific variant
        Arguments:
            product_id {str/int} -- Id of the product in Shopify
            variant_id {str/int} -- Id of the variant in Shopify
            params {dict} -- List of params to be passed on the get call
            session {[aiohttp.ClientSession]} -- AioHttp client session to use in request
        Returns:
            list -- The response list from shopify containing the variant metafields
        """
        logger.info(f'Get metafields for product ID {product_id} and variant ID {variant_id}')

        url= '{url}products/{product_id}/variants/{variant_id}/metafields.json'.format(
            url=self.url, product_id=product_id, variant_id=variant_id)

        logger.info(f'Calling {url} with payload {json.dumps(params)}')

        async with await session.get(url=url, headers=self.auth_header, params=params) as response:
            used, maximum= _get_rate_limits(response)
            if used and maximum:
                session.update_threshold(used, maximum)
            response.raise_for_status()
            metafields_response= []
            metafields_response += (await response.json()).get('metafields', [])

            logger.info(f'Returned metafields: \n{json.dumps(metafields_response, indent=4)}')

            return metafields_response

    async def get_product_count(self, session, params={}):
        """
        Get shopify list of products filtered to only show the variants
        Arguments:
            page {int} -- Page number to get describition from
            session {[aiohttp.ClientSession]} -- AioHttp client session to use in request
        Returns:
            list -- The response list from shopify containing the variants
        """
        logger.info(f'Get product count')

        url= '{url}products/count.json'.format(
            url=self.url)

        logger.info(f'Calling {url}')

        async with await session.get(url=url, headers=self.auth_header, params=params) as response:
            used, maximum= _get_rate_limits(response)
            if used and maximum:
                session.update_threshold(used, maximum)
            response.raise_for_status()
            product_count = (await response.json()).get('count', 0)

            logger.info(f'Returned product count: {product_count}')

            return product_count

    async def set_inventory_level(self, inv_item_id, location_id, atp=0):
        logger.info(f'Setting inventory ATP 0 for inventory_item_id {inv_item_id} and location_id {location_id}')
        
        url_inventory = f'{self.url}inventory_levels/set.json'
        
        inventory_data = {
            'inventory_item_id': int(inv_item_id),
            'location_id': int(location_id),
            'available': atp
        }
        
        logger.debug(f'Calling {url_inventory} with payload {json.dumps(inventory_data)}')

        async with aiohttp.ClientSession() as session:
            async with await session.post(url=url_inventory, headers=self.auth_header, json=inventory_data) as response:
                response_body = await response.json()
                if response.status == 429:
                    logger.warning('Shopify shop api limit reached')
                    return await asyncio.ensure_future(
                        self.set_inventory_level(inv_item_id, location_id,  session))
                if 'errors' in response_body:
                    raise Exception(response_body['errors'][0])
                response.raise_for_status()
                logger.info(f'Response: {json.dumps(response_body)}')
                return response_body

    async def get_inventory_level(self, inv_item_id, location_id, atp=0):
        logger.info(f'Getting inventory levels for inventory_item_id {inv_item_id} and location_id {location_id}')
        
        url_inventory = f'{self.url}inventory_levels.json'
        
        inventory_data = {
            'inventory_item_ids': int(inv_item_id),
            'location_ids': int(location_id)
        }
        
        logger.debug(f'Calling {url_inventory} with params {json.dumps(inventory_data)}')

        async with aiohttp.ClientSession() as session:
            async with await session.get(url=url_inventory, headers=self.auth_header, params=inventory_data) as response:
                response_body = await response.json()
                if response.status == 429:
                    logger.warning('Shopify shop api limit reached')
                    return await asyncio.ensure_future(
                        self.get_inventory_level(inv_item_id, location_id,  session))
                response.raise_for_status()
                logger.debug(f'Response: {json.dumps(response_body)}')
                return response_body.get('inventory_levels')

def _get_rate_limits(response):
    try:
        thresholds= response.headers.get(
            'HTTP_X_SHOPIFY_SHOP_API_CALL_LIMIT')
        if thresholds:
            thresholds= thresholds.split('/')
            return int(thresholds[0]), int(thresholds[1])
        else:
            return None, None
    except Exception:
        logger.exception('Failed to get rate limits: %s', str(response))
        return None, None


def _get_percentage_rate(used, maximum):
    return (float(used) / float(maximum)) * 100.0
