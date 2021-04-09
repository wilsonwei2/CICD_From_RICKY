import aiohttp
import asyncio
import logging
import json
from netsuite_event_stream_receiver.handlers.error import raise_error_if_exists

token = None


class NShandler():
    host = None
    username = None
    password = None

    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password

    async def get_token(self) -> dict:
        global token
        if token:
            return token['access_token']
        else:
            url = 'https://{host}/v0/token'.format(host=self.host)
            headers = {
                'Host': self.host
            }
            form = {
                'grant_type': 'password',
                'username': self.username,
                'password': self.password
            }
            async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
                async with session.post(url=url, headers=headers, data=form) as response:
                    token = await raise_error_if_exists(response)
                    return token['access_token']

    async def graphql_req(self, query, variables=None) -> dict:
        url = f'https://{self.host}/api/v1/org/data/query'
        header = {
            'Authorization': 'Bearer {token}'.format(token=(await self.get_token())),
            'content-type': 'application/json'
        }
        payload = {'query': query}
        if variables:
            payload['variables'] = variables
        async with aiohttp.ClientSession(loop=asyncio.get_event_loop()) as session:
            async with session.post(url=url, headers=header, json=payload) as response:
                response = await raise_error_if_exists(response)
                return response
