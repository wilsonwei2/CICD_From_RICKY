import json
import os
import csv
from param_store.client import ParamStore
from newstore_adapter.connector import NewStoreConnector

TENANT = os.environ.get('TENANT')
STAGE = os.environ.get('STAGE')


class Utils():
    _countries = {}
    _param_store = None
    _newstore_conn = None
    _newstore_config = {}
    _newstore_tenant = None

    @staticmethod
    def get_countries_map():
        if not Utils._countries:
            filename = os.path.join(os.path.dirname(__file__), 'iso_country_codes.csv')
            with open(filename) as country_file:
                file = csv.DictReader(country_file, delimiter=',')
                for line in file:
                    Utils._countries[line['Alpha-2 code']] = Utils._format_country_name(
                        line['English short name lower case'])
        return Utils._countries

    @staticmethod
    def _format_country_name(country_name):
        func = lambda s: s[:1].lower() + s[1:] if s else ''
        return f'_{func(country_name).replace(" ", "")}'

    # Gets the information about the discounts of an item
    @staticmethod
    def get_discount_info(item):
        has_item_discount = float(item['item_discounts']) > 0
        has_order_discount = float(item['order_discounts']) > 0
        has_discount = has_item_discount or has_order_discount
        total_discount = abs(
            float(item['item_discounts']) + float(item['order_discounts']))

        return has_item_discount, has_order_discount, has_discount, total_discount

    @staticmethod
    def _get_param_store():
        if not Utils._param_store:
            Utils._param_store = ParamStore(tenant=TENANT,
                                            stage=STAGE)
        return Utils._param_store

    @staticmethod
    def _get_newstore_config():
        if not Utils._newstore_config:
            Utils._newstore_config = json.loads(
                Utils._get_param_store().get_param('newstore'))
        return Utils._newstore_config

    @staticmethod
    def get_newstore_conn(context=None):
        if not Utils._newstore_conn:
            newstore_creds = Utils._get_newstore_config()
            Utils._newstore_conn = NewStoreConnector(tenant=newstore_creds['tenant'], context=context,
                                                     username=newstore_creds['username'],
                                                     password=newstore_creds['password'], host=newstore_creds['host'],
                                                     raise_errors=True)
        return Utils._newstore_conn

    @staticmethod
    def get_newstore_tenant():
        if not Utils._newstore_tenant:
            newstore_creds = Utils._get_newstore_config()
            Utils._newstore_tenant = newstore_creds['tenant']

        return Utils._newstore_tenant

