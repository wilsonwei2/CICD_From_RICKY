import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)


class Token():
    host = None
    username = None
    password = None
    token = None

    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.loop = asyncio.get_event_loop()



    def get_token(self):
        return self.loop.run_until_complete(self.__get_token())


    async def __get_token(self):
        if self.token:
            LOGGER.info(
                'Token already exists %s', self.token)
            return self.token['access_token']
        else:
            logger.info(
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
            except Exception as e:
                logger.info("TokenHandler - Not able to get the token")
                raise



