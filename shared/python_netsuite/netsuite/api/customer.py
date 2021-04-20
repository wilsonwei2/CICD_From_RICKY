from netsuite.client import client, passport, app_info, make_passport
from netsuite.utils import (
    get_record_by_type,
    search_records_using,
    format_error_message
)
from netsuite.service import (
    Customer,
    CustomerAddressbook,
    CustomerAddressbookList,
    CustomerSearchBasic,
    SearchStringField,
    SearchMultiSelectField,
    RecordRef,
    SearchBooleanField
)
import uuid
from collections.abc import Mapping
import logging
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




def get_customer(internal_id):
    return get_record_by_type('customer', internal_id)


def create_customer(customer_data, return_customer_id=False):
    customer = Customer(**customer_data) if isinstance(customer_data, Mapping) else customer_data

    logger.debug("Customer sent to NetSuite: \n%s" % customer)

    response = client_service_add(customer)
    r = response.body.writeResponse

    logger.debug("Response: \n%s" % response)

    if r.status.isSuccess:
        internal_id = r.baseRef.internalId
        return internal_id if return_customer_id else get_customer(internal_id)
    else:
        raise Exception(format_error_message(r.status.statusDetail))


def update_customer(customer_data):
    customer = Customer(**customer_data) if isinstance(customer_data, Mapping) else customer_data

    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.update(customer, _soapheaders={
            'tokenPassport': make_passport(),
        })
    else:
        response = client.service.update(customer, _soapheaders={
            'passport': passport,
            'applicationInfo': app_info
        })

    r = response.body.writeResponse
    if r.status.isSuccess:
        internal_id = r.baseRef.internalId
        return get_customer(internal_id)
    else:
        raise Exception(format_error_message(r.status.statusDetail))


def create_customer_address_book(customer_address_book_data):
    customer_address_book_data['entityId'] = str(uuid.uuid4())
    customer_address_book = CustomerAddressbook(**customer_address_book_data)

    response = client_service_add(customer_address_book)

    r = response.body.writeResponse
    print (r.response)
    if r.status.isSuccess:
        return True
    raise Exception(format_error_message(r.status.statusDetail))


def lookup_customer_id_by_name_and_email(customer_data, return_customer_id=True):
    name_and_email = {k: v for k, v in customer_data.items()
                      if k in ['firstName', 'lastName', 'email']}
    search_fields = {k: SearchStringField(searchValue=v, operator='is')
                     for k, v in name_and_email.items()}
    # Add subsidiary on search to create clients in all subsidiaries needed
    search_fields['subsidiary'] = SearchMultiSelectField(
        searchValue=[RecordRef(internalId=customer_data['subsidiary']['internalId'])],
        operator='anyOf'
    )
    # Get only active Customer records
    search_fields['isInactive'] = SearchBooleanField(
        searchValue=False
    )
    customer_search = CustomerSearchBasic(**search_fields)

    logger.info(f"Searching NetSuite with: {name_and_email}. Subsidiary: {customer_data['subsidiary']['internalId']}")

    response = search_records_using(customer_search)

    r = response.body.searchResult
    if r.status.isSuccess:
        if r.recordList is None:
            return
        records = r.recordList.record
        if len(records) > 0:
            if return_customer_id:
                return records[0].internalId
            return records[0]


def lookup_customer_id_by_email(customer_data, return_customer_id=True):
    search_fields = {
        "email": SearchStringField(
            searchValue=customer_data['email'],
            operator='is'
        ),
        # Add subsidiary on search to create clients in all subsidiaries needed
        "subsidiary": SearchMultiSelectField(
            searchValue=[RecordRef(internalId=customer_data['subsidiary']['internalId'])],
            operator='anyOf'
        ),
        # Get only active Customer records
        "isInactive": SearchBooleanField(
            searchValue=False
        )
    }

    customer_search = CustomerSearchBasic(**search_fields)

    logger.info(f"Searching NetSuite with email: {customer_data['email']} and subsidiary: {customer_data['subsidiary']['internalId']}")

    response = search_records_using(customer_search)

    r = response.body.searchResult
    if r.status.isSuccess:
        if r.recordList is None:
            return
        records = r.recordList.record
        if len(records) > 0:
            if return_customer_id:
                return records[0].internalId
            return records[0]
