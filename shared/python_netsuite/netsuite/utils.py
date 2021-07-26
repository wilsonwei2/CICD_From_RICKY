import re, os
import logging

from netsuite.client import client, app_info, passport, make_passport
from netsuite.service import (
    RecordRef,
    SearchPreferences
)
from datetime import datetime, date
logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)


class obj(object):
    """Dictionary to object utility.

    >>> d = {'b': {'c': 2}}
    >>> x = obj(d)
    >>> x.b.c
    2
    """
    def __init__(self, d):
        for a, b in d.items():
            if isinstance(b, (list, tuple)):
               setattr(self, a, [obj(x)
                   if isinstance(x, dict) else x for x in b])
            else:
               setattr(self, a, obj(b)
                   if isinstance(b, dict) else b)


def get_record_by_type(type, internal_id):
    record = RecordRef(internalId=internal_id, type=type)

    if os.environ.get('netsuite_tba_active', '0') == "1":
        response = client.service.get(record,
            _soapheaders={
                'tokenPassport': make_passport(),
            }
        )
    else:
        response = client.service.get(record,
            _soapheaders={
                'applicationInfo': app_info,
                'passport': passport,
            }
        )

    logger.info(f'get_record_by_type Response: {response}')

    r = response.body.readResponse
    if r.status.isSuccess:
        return r.record


def search_records_using(searchtype, pageSize=20):
    search_preferences = SearchPreferences(
        bodyFieldsOnly=False,
        returnSearchColumns=True,
        pageSize=pageSize
    )

    if os.environ.get('netsuite_tba_active', '0') == "1":

        response =  client.service.search(
            searchRecord=searchtype,
            _soapheaders={
                'searchPreferences': search_preferences,
                'tokenPassport': make_passport(),
            }
        )
    else:
        response =  client.service.search(
            searchRecord=searchtype,
            _soapheaders={
                'searchPreferences': search_preferences,
                'applicationInfo': app_info,
                'passport': passport
            }
        )

    return response


def format_error_message(statusDetail):
    err_messages = []
    for status in statusDetail:
        err_messages.append(f"{status.type} - {status.code}: {status.message}")
    return '; \n'.join(err_messages)


###
# Formats the phone to a valid number to be injected into NetSuite
# phone: phone to be validated and formated
# return: phone in the format 555-555-5555 which is acceptable by NetSuite
# Documentation from NetSuite:
# Must be entered in the following formats:999-999-9999, 1-999-999-9999, (999) 999-9999, 1(999) 999-9999 or 999-999-9999 ext 9999.
# Additional info:
# Accepts international numbers (e.g. +44 09999 999999)
# but returns phone in NetSuite acceptable format (e.g. 999-999-9999 without +44)
###
def get_formated_phone(phone):
    phone = phone.replace(' ', '')
    regex = r'^\(?(\+[0-9]{1,3})?\)?\D?\d?\D?(\d{3})\D?\D?(\d{3})\D?(\d{4})$'
    phone = phone if re.match(regex, phone) else '5555555555'
    phone = re.sub(regex, r'\2-\3-\4', phone)
    return phone


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))
