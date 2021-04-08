# -*- coding: utf-8 -*-
import hashlib
import base64
import hmac
import sys
import logging

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def verify_webhook(data, hmac_header, secret):
    return _calculate_hmac(data, secret) == hmac_header


def _calculate_hmac(data, secret):
    hash_hmac = hmac.new(secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha256)
    calculated_hmac = base64.b64encode(hash_hmac.digest()).decode('utf-8')
    return calculated_hmac
