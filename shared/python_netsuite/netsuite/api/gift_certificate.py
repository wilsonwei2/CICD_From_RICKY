from netsuite.client import client, passport, app_info, make_passport
from netsuite.service import (
    GiftCertificate,
    GiftCertificateSearchBasic,
    SearchStringField
)

from netsuite.utils import get_record_by_type, search_records_using
import os


def create_gift_certificate(data):
    gift_certificate = GiftCertificate(**data)

    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.add(
            gift_certificate,
            _soapheaders={
                'tokenPassport': make_passport(),
            }
        )
    else:
        response = client.service.add(
            gift_certificate,
            _soapheaders={
                'passport': passport,
                'applicationInfo': app_info
            }
        )

    r = response.body.writeResponse
    if r.status.isSuccess:
        result = get_record_by_type('giftCertificate', r.baseRef.internalId)
        return True, result
    return False, r


def get_gift_certificate(giftCertCode):
    gift_certificate_search = GiftCertificateSearchBasic(
        giftCertCode=SearchStringField(
            searchValue=giftCertCode,
            operator='is'
        ))
    result = search_records_using(gift_certificate_search)
    r = result.body.searchResult
    if r.status.isSuccess:
        # The search can return nothing, meaning the gift card doesn't exist in NetSuite
        if r.recordList:
            return r.recordList.record[0]
    return None
