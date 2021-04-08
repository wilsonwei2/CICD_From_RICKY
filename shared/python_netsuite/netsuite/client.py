from netsuite import ns_config
from netsuite.service import (
    client,
    RecordRef,
    ApplicationInfo,
    Passport,
    TokenPassport,
    TokenPassportSignature

)

import base64
import hashlib
import hmac
import logging
import random
import time
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)


"""
User Based authentification
"""
def make_passport2():
    role = RecordRef(internalId=ns_config.NS_ROLE)
    return Passport(email=ns_config.NS_EMAIL,
                    password=ns_config.NS_PASSWORD,
                    account=ns_config.NS_ACCOUNT,
                    role=role)


"""
Token Based Authentification 
"""
def make_passport():
    # Only process this if tba is enabled in the lambda, otherwise there will be a module initialization error
    if not os.environ.get('netsuite_tba_active', '0') == "1":
        return None

    def compute_nonce(length=20):
        """pseudo-random generated numeric string"""
        return ''.join([str(random.randint(0, 9)) for i in range(length)])

    nonce = compute_nonce(length=20)
    consumer_key = os.environ.get('netsuite_consumer_key')
    consumer_secret = os.environ.get('netsuite_consumer_secret')
    token_key = os.environ.get('netsuite_token_key')
    token_secret = os.environ.get('netsuite_token_secret')
    account = os.environ.get('netsuite_account_id')

    signature_algorithm = "HMAC-SHA256"
    timestamp = str(int(time.time()))
    key = '{}&{}'.format(consumer_secret, token_secret)
    base_string = '&'.join([account, consumer_key, token_key, nonce, str(timestamp)])
    key_bytes = key.encode(encoding='ascii')
    message_bytes = base_string.encode(encoding='ascii')
    hashed_value = hmac.new(key_bytes, msg=message_bytes, digestmod=hashlib.sha256)
    dig = hashed_value.digest()
    value = base64.b64encode(dig).decode()
    signature = TokenPassportSignature(value, algorithm=signature_algorithm)

    return TokenPassport(account=account, consumerKey=consumer_key, token=token_key, nonce=nonce, timestamp=timestamp,
                         signature=signature)


def login():
    app_info = ApplicationInfo(applicationId=ns_config.NS_APPID)

    if os.environ.get('netsuite_tba_active', '0') == '1':
        logger.info('netsuite_tba_active flag is on. Connection to NetSuite will be facilitated using Token Based'
                    ' Authentication.')

    if os.environ.get('netsuite_disable_login', '0') == '1':
        logger.info('netsuite_disable_login flag is on. Will not login to NetSuite. Login is not required for Token '
                    'Based Authentication (TBA)')
    else:
        passport = make_passport2()
        login = client.service.login(passport=passport,
          _soapheaders={'applicationInfo': app_info})

        logger.info('Login Response: %s' % login['status'])

    return client, app_info


passport = make_passport2()
tokenpassword = make_passport()
client, app_info = login()
