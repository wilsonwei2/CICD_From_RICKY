import aiobotocore
import asyncio
import json


async def start_lambda_function(lambda_name, payload={}):
    loop = asyncio.get_event_loop()
    lambda_session = aiobotocore.get_session()
    async with lambda_session.create_client('lambda') as client:
        return (await client.invoke(FunctionName=lambda_name, InvocationType='Event', Payload=json.dumps(payload)))
