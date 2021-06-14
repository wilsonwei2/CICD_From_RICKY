# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.
import logging

from shopify_payment_adaptor.handlers.shopify_handler import ShopifyConnector
from shopify_payment_adaptor.utils.utils import get_shopify_handler

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


async def activate_card(amount, currency, customer_id):
    """
    Create a new gift card and activate it
    """
    assert amount, 'Could not get ammount'

    try:
        handler = get_shopify_handler(currency)
        LOGGER.info(f'Shopify Customer ID is -- {customer_id}')
        resp = await handler.active_gift_card(amount=amount, currency=currency, customer_id=customer_id)
        return resp
    except AssertionError:
        raise
    except TypeError as e:
        LOGGER.error(e)
        try:
            raise str(e).split('activate() ')[1].capitalize()
        except Exception:
            raise Exception('Bad input')
    except Exception:
        raise


async def adjust_gift_card(card_number: str, amount: float, reason: str, currency: str=None):
    """
    Adjust the value of a gift card
    """
    try:
        handler = get_shopify_handler(currency)
        LOGGER.info(f'Shopify Gift Card Number is -- {card_number}')
        resp_gift_card = await handler.search_gift_card(card_number)
        if len(resp_gift_card['gift_cards']) == 0:
            LOGGER.error('Cannot find the Gift Card to adjust at shopify')
            raise Exception('Cannot find gift card on shopify')
        resp_adjust = await handler.adjust_gift_card(
            resp_gift_card['gift_cards'][0]['id'],
            amount,
            reason
        )
        LOGGER.info(resp_adjust)
        return resp_adjust
    except AssertionError:
        raise
    except TypeError as e:
        try:
            raise str(e).split('activate() ')[1].capitalize()
        except Exception:
            raise Exception('Bad input')
    except Exception:
        raise
