# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.

import os, json, logging, asyncio
from requests import post
from param_store.client import ParamStore
from shopify_gift_card.aws.shopify_gift_card_balance import _get_card, TENANT, STAGE

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

'''
Lambda for activating and issuing gift card with shopify

For use with API Gateway
'''


def handler(event, context):
    LOGGER.debug(json.dumps(event, indent=2))

    is_issue = event['path'].endswith('/issue')
    LOGGER.info(f'Is issue: {is_issue}')
    try:
        body = json.loads(event['body'])
        if not is_issue:
            assert body.get('card_number')
        assert body.get('amount')
        assert {'value', 'currency'} <= body['amount'].keys()
    except Exception as e:
        LOGGER.exception(str(e), exc_info=True)
        return _400_error('Bad input')
    
    try:
        resp = activate(is_issue, **body)
    except AssertionError as e:
        LOGGER.exception(str(e), exc_info=True)
        return _400_error(body=e.data)
    except TypeError as e:
        LOGGER.exception(str(e), exc_info=True)
        try:
            return _400_error(str(e).split('activate() ')[1].capitalize())
        except Exception:
            LOGGER.exception(str(e), exc_info=True)
            return _400_error('Bad input')

    if isinstance(resp, AssertionError):
        LOGGER.warn(resp.data)
        return _400_error(body=resp.data)

    LOGGER.debug(f'resp: {resp}')
    # Pretty hacky
    if '"error_code":' in resp:
        return _400_error(body=resp)

    return {
        "isBase64Encoded": False,
        "statusCode": 200,
        "headers": {
            "content-type": 'application/json'
        },
        "body": resp
    }


def activate(is_issue: bool, amount: dict, card_number: str=None, idempotence_key: str=None, correlation_id: str=None, **kwargs):
    LOGGER.info('Activate')
    if correlation_id and not is_issue:
        raise TypeError(
            "activate() got an unexpected keyword argument 'correlation_id'")
    if is_issue:
        if idempotence_key:
            raise TypeError(
                "activate() got an unexpected keyword argument 'idempotence_key'")
        if card_number:
            raise TypeError(
                "activate() got an unexpected keyword argument 'card_number'")
    if card_number.startswith('shopify-giftcard-v1-'):
        card_number = card_number[20:]
    
    param_store = ParamStore(TENANT, STAGE)
    shopify_config = json.loads(param_store.get_param('shopify'))

    loop = asyncio.get_event_loop()
    cards = loop.run_until_complete(_get_card(card_number, shopify_config))

    card = None
    if len(cards) > 0:
        for c in cards:
            if card_number.endswith(c['last_characters']):
                card = c
                break
    if card and not card['disabled_at']:
        LOGGER.info('Card already exist and is activated, returning it %s', json.dumps(card))
        resp =  {
            'identifier': {
                'number': card_number
            }
        }  
    else:
        shop = shopify_config['shop']
        host = 'myshopify.com/admin'

        AUTH = (shopify_config['username'], shopify_config['password'])
        payload = {
            'gift_card': {
                'code': card_number,
                'initial_value': amount['value'],
                'currency': amount['currency'].upper()
            }
        }
        
        LOGGER.info(f'POST https://{shop}.{host}/gift_cards.json')
        LOGGER.info(json.dumps(payload, indent=4))

        r = post(f"https://{shop}.{host}/gift_cards.json", auth=AUTH, json=payload)
        if not r.ok:
            e = AssertionError()
            e.data = {'error_code': str(r.status_code), 'message': r.reason,
                      'details': r.json(), 'request_accepted': False}
            return e
        resp = {
            'identifier': {
                'number': r.json()['gift_card']['code']
            }
        }

    if correlation_id:
        resp['correlation_id'] = correlation_id
    resp = json.dumps(resp)
    return resp


def _400_error(error_code='', message='', request_accepted=False, body=None) -> dict:
    assert bool(error_code) ^ bool(body), 'Must supply error_code or body'
    if isinstance(body, dict):
        body = json.dumps(body)
    assert isinstance(body, (str, type(None)))
    return {
        "isBase64Encoded": False,
        "statusCode": 400,
        "headers": {
            "content-type": 'application/json'
        },
        "body": body if body else f'{{"error_code": "{error_code}", "message": "{message}", "request_accepted": {json.dumps(request_accepted)}}}'
    }
