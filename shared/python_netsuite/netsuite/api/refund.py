from netsuite.client import client, passport, app_info, make_passport
from netsuite.service import (
    CashRefund,
    CreditMemo
)
from netsuite.utils import get_record_by_type, json_serial
from netsuite.api.sale import get_transaction

from zeep.helpers import serialize_object

import logging
import json
import os

logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)

def client_service_add(item):
    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.add(item, _soapheaders={
            'tokenPassport': make_passport(),
        })
    else:
        response = client.service.add(item, _soapheaders={
            'passport': passport,
            'applicationInfo': app_info
        })
    return response


def create_cash_refund(data):
    refund = CashRefund(**data)

    logger.debug('CashRefund: \n%s' % json.dumps(serialize_object(refund), indent=4, default=json_serial))

    response = client_service_add(refund)

    logger.info(f'Response: {response}')
    
    r = response.body.writeResponse
    if r.status.isSuccess:
        record_type = 'cashRefund'
        result = get_record_by_type(record_type, r.baseRef.internalId)
        return True, result
    return False, r


def create_credit_memo(data):
    refund = CreditMemo(**data)

    logger.debug('CreditMemo: \n%s' % json.dumps(serialize_object(refund), indent=4, default=json_serial))

    response = client_service_add(refund)

    logger.info(f'Response: {response}')
    
    r = response.body.writeResponse
    if r.status.isSuccess:
        record_type = 'creditMemo'
        result = get_record_by_type(record_type, r.baseRef.internalId)
        return True, result
    return False, r


def get_credit_memo(externalId):
    return get_transaction(externalId, '_creditMemo')
