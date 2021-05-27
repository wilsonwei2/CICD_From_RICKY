# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.

from requests import get
from param_store.client import ParamStore
import aiohttp
import asyncio
import json, os
import logging

LOGGER=logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

TENANT = os.environ['TENANT'] or 'frankandoak'
STAGE = os.environ['STAGE'] or 'x'
# Shopify channels/accounts to check for gift cards
SHOPIFY_CHANNELS = json.loads(os.environ.get('SHOPIFY_CHANNELS', '["US"]'))


'''
Lambda for getting gift card balance from shopify
For use with API Gateway
'''
def handler(event, context):
    LOGGER.info('Get balance check: %s', event['body'])

    try:
        card_number = json.loads(event['body'])['identifier']['number']
    except Exception:
        return _400_error('Bad input')

    try:
        LOGGER.info('Getting gift card balance')
        resp = get_balance(card_number)
        LOGGER.info('Shopify gift card balance: %s', json.dumps(resp))
    except AssertionError as e:
        return _400_error(str(e))

    return {
        "isBase64Encoded": False,
        "statusCode": 200,
        "headers": {
            "content-type": 'application/json'
        },
        "body": json.dumps(resp)
    }


def get_balance(number: str) -> dict:
    param_store = ParamStore(TENANT, STAGE)
    shopify_config = json.loads(param_store.get_param('shopify'))

    loop = asyncio.get_event_loop()
    cards = loop.run_until_complete(_get_card(number, shopify_config))

    if len(cards) == 1:
        card = cards[0]
    elif len(cards) > 1:
        assert len(set((i['last_characters'] for i in cards))) == len(cards), 'Multiple matches'
        for c in cards:
            if number.endswith(c['last_characters']):
                card = c
                break
        else:
            LOGGER.warn('Could not match the card id')
            raise AssertionError('No match 1')
    else:
        LOGGER.warn('Could not find the requested gift card')
        raise AssertionError('No match 2')

    assert not card['disabled_at'], 'Disabled'
    return {'value': float(card['balance']), 'currency': card['currency']}


async def _get_card(number: str, shopify_config: dict) -> dict:
    gift_cards = []
    tasks = []
    async with aiohttp.ClientSession() as session:
        auth = aiohttp.BasicAuth(shopify_config['username'], shopify_config['password'])
        shop = shopify_config['shop']
        host = 'myshopify.com/admin'

        LOGGER.info(f'Requesting gift card {number} from shopify account {shop}')

        response = await _fetch_gift_cards(
                session,
                f'https://{shop}.{host}/gift_cards/search.json',
                auth,
                {'query': f'code:{number}'}
            )

        gift_cards = response.get('gift_cards', [])
        LOGGER.info(f'giftcard fetched : {json.dumps(gift_cards)}')

    return gift_cards


async def _fetch_gift_cards(session, url, auth, params):
    async with session.get(url, auth=auth, params=params) as response:
        return await response.json()


def _400_error(error_code: str, message='', request_accepted=False) -> dict:
    LOGGER.info(f'Error Occurder: {message}')

    return {
            "isBase64Encoded": False,
            "statusCode": 400,
            "headers": {
                "content-type": 'application/json'
            },
            "body": f'{{"error_code": "{error_code}", "message": "{message}", "request_accepted": {json.dumps(request_accepted)}}}'
        }
