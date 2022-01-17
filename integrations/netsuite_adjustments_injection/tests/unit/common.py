import os, sys, json
from datetime import date, datetime


def setup_environment_variables():
    os.environ['SQS_QUEUE'] = 'SQS_QUEUE'
    os.environ['netsuite_account_id'] = '100000'
    os.environ['netsuite_application_id'] = 'NOT_SET'
    os.environ['netsuite_email'] = 'NOT_SET'
    os.environ['netsuite_password'] = 'NOT_SET'
    os.environ['netsuite_role_id'] = 'NOT_SET'
    os.environ['netsuite_wsdl_url'] = 'https://webservices.netsuite.com/wsdl/v2018_1_0/netsuite.wsdl'


def assert_json(test_case, json1, json2):
    if isinstance(json1, (datetime, date)):
        json1 = json1.isoformat()
    if isinstance(json2, (datetime, date)):
        json2 = json2.isoformat()
    if isinstance(json1, dict):
        for key, value in json1.items():
            assert_json(test_case, value, json2[key])
    elif isinstance(json1, list):
        for i, value in enumerate(json1):
            assert_json(test_case, value, json2[i])
    else:
        test_case.assertEqual(json1, json2)


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))
