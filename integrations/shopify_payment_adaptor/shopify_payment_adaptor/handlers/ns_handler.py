import aiohttp
import asyncio
import logging

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class NShandler():
    host = None
    username = None
    password = None
    token = None

    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password

    async def get_token(self):
        if self.token:
            LOGGER.info(
                f'Token already exists ${self.token}')
            return self.token['access_token']
        else:
            LOGGER.info(
                f'Getting token from newstore {self.host}')
            url = f'https://{self.host}/v0/token'
            headers = {
                'Host': self.host
            }
            form = {
                'grant_type': 'password',
                'username': self.username,
                'password': self.password
            }
            try:
                async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
                    async with session.post(url=url, headers=headers, data=form) as response:
                        response.raise_for_status()
                        self.token = await response.json()
                        return self.token['access_token']
            except Exception as ex:
                LOGGER.error(f'Exception in ns handler: ${str(ex)}')
                raise

    async def get_return_orders(self, order_id, return_id):
        """
        Get Newstore returns associated with an order
        """
        url = f'https://{self.host}/v0/d/orders/{order_id}/returns/{return_id}'
        LOGGER.info(
            f'Getting returns from newstore ${url}')
        header = {
            'Authorization': 'Bearer {token}'.format(token=await self.get_token())
        }
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=url, headers=header) as response:
                response.raise_for_status()
                return await response.json()

    async def get_order_by_external_id(self, order_id):
        """
        Get Newstore order based on country_code, zip and email,
        country_code can be empty
        """
        url = 'https://{host}/v0/d/external_orders/{order_id}'.format(
            host=self.host, order_id=order_id)
        LOGGER.info(
            f'Getting order values from newstore ${url}')
        header = {
            'Authorization': 'Bearer {token}'.format(token=await self.get_token())
        }
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=url, headers=header) as response:
                response.raise_for_status()
                return await response.json()

    async def get_order(self, order_id):
        """
        Get Newstore order based on country_code, zip and email,
        country_code can be empty
        """
        url = f'https://{self.host}/v0/c/orders/{order_id}'
        LOGGER.info(
            f'Getting order values from newstore ${url}')
        header = {
            'Authorization': 'Bearer {token}'.format(token=await self.get_token())
        }
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.patch(url=url, headers=header, json={}) as response:
                response.raise_for_status()
                return await response.json()

    async def get_customer_order(self, order_id):
        """
        Get Newstore order based on country_code, zip and email,
        country_code can be empty
        """
        url = f'https://{self.host}/v0/c/customer_orders/{order_id}'
        LOGGER.info(
            f'Getting order values from newstore ${url}')
        header = {
            'Authorization': 'Bearer {token}'.format(token=await self.get_token())
        }
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=url, headers=header) as response:
                response.raise_for_status()
                return await response.json()

    async def get_refund(self, order_id, refund_id):
        """
        Get Newstore order based on country_code, zip and email,
        country_code can be empty
        """
        url = f'https://{self.host}/v0/d/orders/{order_id}/refunds/{refund_id}'
        LOGGER.info(
            f'Getting order values from newstore ${url}')
        header = {
            'Authorization': 'Bearer {token}'.format(token=await self.get_token())
            }
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=url, headers=header) as response:
                response.raise_for_status()
                return await response.json()

    async def get_order_note(self, order_id: str):
        url = f'https://{self.host}/v0/d/orders/{order_id}/notes'
        LOGGER.info("GET Order Note")
        header = {
            'Authorization': 'Bearer {token}'.format(token=await self.get_token())
        }
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=url, headers=header) as response:
                response.raise_for_status()
                return await response.json()

    async def delete_order_note(self, order_id: str, note_id: str):
        url = f'https://{self.host}/v0/d/orders/{order_id}/notes/{note_id}'
        LOGGER.info("Delete Order Note")
        header = {
            'Authorization': 'Bearer {token}'.format(token=await self.get_token())
        }
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.delete(url=url, headers=header) as response:
                response.raise_for_status()
                return await response.json()
