import hashlib
import base64
import hmac


def verify_webhook(data, hmac_header, secret):
    digest = hmac.new(secret.encode(), data.encode(), hashlib.sha256).digest()
    computed_hmac = base64.b64encode(digest)
    return hmac.compare_digest(computed_hmac, hmac_header.encode())
