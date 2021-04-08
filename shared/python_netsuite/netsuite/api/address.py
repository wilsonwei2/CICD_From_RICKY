from netsuite.client import client, passport, app_info, make_passport
from netsuite.utils import (
    get_record_by_type,
    search_records_using
)
from netsuite.service import (
    Address,
    AddressSearchBasic,
    SearchStringField
)
import uuid
import os


def get_address(internal_id):
    return get_record_by_type('address', internal_id)


def create_address(address_data):
    """
    Lookup address, add a address if lookup fails.
    """
    address_data['entityId'] = str(uuid.uuid4())
    address = Address(**address_data)

    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.add(address, _soapheaders={
            'tokenPassport': make_passport(),
        })
    else:
        response = client.service.add(address, _soapheaders={
            'passport': passport,
            'applicationInfo': app_info
        })

    r = response.body.writeResponse
    if r.status.isSuccess:
        internal_id = r.baseRef.internalId

    return get_address(internal_id)
