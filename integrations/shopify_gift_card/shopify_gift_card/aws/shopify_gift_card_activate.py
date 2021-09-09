# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.

import json
import logging
import asyncio
from requests import post
from pom_common.shopify import ShopManager
from shopify_gift_card.aws.shopify_gift_card_balance import _get_card, TENANT, STAGE, REGION

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

# Lambda for activating and issuing gift card with shopify
# For use with API Gateway

def handler(event, _): # pylint: disable=R0911
    LOGGER.info(json.dumps(event, indent=2))

    is_issue = event['path'].endswith('/issue')
    LOGGER.info(f'Is issue: {is_issue}')
    try:
        body = json.loads(event['body'])
        if not is_issue:
            assert body.get('card_number')
        assert body.get('amount')
        assert {'value', 'currency'} <= body['amount'].keys()
    except Exception as e: # pylint: disable=W0703
        LOGGER.exception(str(e), exc_info=True)
        return _400_error('Bad input')

    try:
        resp = activate(is_issue, **body)
    except AssertionError as e:
        LOGGER.exception(str(e), exc_info=True)
        return _400_error(body=str(e))
    except TypeError as e:
        LOGGER.exception(str(e), exc_info=True)
        try:
            return _400_error(str(e).split('activate() ')[1].capitalize())
        except Exception: # pylint: disable=W0703
            LOGGER.exception(str(e), exc_info=True)
            return _400_error('Bad input')

    if isinstance(resp, AssertionError):
        LOGGER.warning(resp.data)
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


def activate(is_issue: bool, amount: dict, card_number: str = None, idempotence_key: str = None, correlation_id: str = None, **_):
    LOGGER.info(f'Activate {card_number}')
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

    currency = amount['currency'].upper()

    shop_manager = ShopManager(TENANT, STAGE, REGION)
    shopify_config = next(
        filter(
            lambda cnf: cnf['currency'] == currency, [shop_manager.get_shop_config(shop_id) for shop_id in shop_manager.get_shop_ids()]),
        None
    )

    LOGGER.info(f'Got Shopify Config {shopify_config["shop"]} to activate gift card for currency {amount["currency"]}')

    loop = asyncio.get_event_loop()
    cards = loop.run_until_complete(_get_card(card_number, shopify_config))

    card = None
    if len(cards) > 0:
        for current_card in cards:
            if card_number.endswith(current_card['last_characters']):
                card = current_card
                break
    if card and not card['disabled_at']:
        LOGGER.info(f'Card already exist and is activated, returning it {json.dumps(card)}')
        resp = {
            'identifier': {
                'number': card_number
            }
        }
    else:
        shop = shopify_config['shop']
        host = 'myshopify.com/admin'

        auth = (shopify_config['username'], shopify_config['password'])
        payload = {
            'gift_card': {
                'code': card_number,
                'initial_value': amount['value'],
                'currency': amount['currency'].upper()
            }
        }

        LOGGER.info(f'POST https://{shop}.{host}/gift_cards.json')
        LOGGER.info(json.dumps(payload, indent=4))

        response = post(f"https://{shop}.{host}/gift_cards.json", auth=auth, json=payload)
        if not response.ok:
            e = AssertionError()
            e.data = {'error_code': str(response.status_code), 'message': response.reason,
                      'details': response.json(), 'request_accepted': False}
            return e
        resp = {
            'identifier': {
                'number': response.json()['gift_card']['code']
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
