import aiohttp
import asyncio
import logging
import os

LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(LOG_LEVEL)


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
        if not self.token:
            LOGGER.info(
                'Getting token from newstore {host}'.format(host=self.host))
            url = 'https://{host}/v0/token'.format(host=self.host)
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
            except:
                raise
        else:
            LOGGER.info(
                'Token already exists %s', self.token)
            return self.token['access_token']

    async def availability_export(self):
        url = 'https://{host}/v0/d/export/availabilities'.format(
            host=self.host)
        LOGGER.info(
            'Getting availabilities values from newstore %s', url)
        header = {
            'Authorization': 'Bearer {token}'.format(token=await self.get_token())
        }
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=url, headers=header) as response:
                response.raise_for_status()
                LOGGER.info('Received inventory numbers')
                return await response.json()

    async def availability_export_dc(self, last_updated_at=None):
        url = 'https://{host}/v0/d/availabilities/bulk'.format(
            host=self.host)
        LOGGER.info(
            'Getting availabilities values from newstore: %s', url)
        header = {
            'Authorization': 'Bearer {token}'.format(token=await self.get_token())
        }
        body = {}
        if last_updated_at:
            body['last_updated_at'] = int(last_updated_at)
            LOGGER.debug('Getting availabiltities after: %s', body)
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.post(url=url, headers=header, json=body) as response:
                response.raise_for_status()
                export = await response.json()
                LOGGER.info('Created export id %s ', export.get('availability_export_id'))
                return export

    async def get_availability_export(self, export_id):
        url = 'https://{host}/v0/d/availabilities/bulk/{export_id}'.format(host=self.host, export_id=export_id)
        LOGGER.info( 'Getting availabilities values from newstore: %s', url )
        header = {
            'Authorization': 'Bearer {token}'.format(token=await self.get_token())
        }
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.get(url=url, headers=header) as response:
                response.raise_for_status()
                export = await response.json()
                LOGGER.info('Export job: %s ', export)
                return export
