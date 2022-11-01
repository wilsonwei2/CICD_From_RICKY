import aiobotocore
from aiobotocore.session import get_session
import asyncio
import json


async def start_lambda_function(lambda_name, payload={}):
    loop = asyncio.get_event_loop()
    lambda_session = get_session()
    async with lambda_session.create_client('lambda') as client:
        return (await client.invoke(FunctionName=lambda_name, InvocationType='Event', Payload=json.dumps(payload)))


def stop_before_timeout(context, time, logger=None):
    if logger:
        remaining_time = context.get_remaining_time_in_millis()
    logger.debug(f'{remaining_time}ms remaining before timeout')
    if remaining_time <= time:
        if logger:
            logger.info(f'Only {remaining_time}ms remaining before timeout, stopping')
        return True
    return False
