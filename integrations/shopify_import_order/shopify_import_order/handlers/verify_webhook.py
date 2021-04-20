# -*- coding: utf-8 -*-
import hashlib
import base64
import hmac


def verify_webhook(data, secret, hmac_header):
    digest = hmac.new(
        secret.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).digest()
    computed_hmac = base64.b64encode(digest)
    is_valid = hmac.compare_digest(computed_hmac, bytes(hmac_header, 'utf-8'))

    return is_valid
