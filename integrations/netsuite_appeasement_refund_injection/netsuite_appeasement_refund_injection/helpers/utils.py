import os
import csv
import json
import logging
from datetime import datetime, date
from pytz import timezone
from pytz.exceptions import UnknownTimeZoneError
from param_store.client import ParamStore
from newstore_adapter.connector import NewStoreConnector

LOGGER = logging.getLogger()
LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'info').upper() or 'INFO'
LOG_LEVEL = getattr(logging, LOG_LEVEL_SET, None)
if not isinstance(LOG_LEVEL, int):
    LOG_LEVEL = getattr(logging, 'INFO', None)
LOGGER.setLevel(LOG_LEVEL)
TENANT = os.environ.get('TENANT_NAME')
STAGE = os.environ.get('NEWSTORE_STAGE')


class Utils():
    _param_store = None
    _newstore_conn = None
    _countries = {}
    _newstore_config = {}
    _netsuite_config = {}
    _newstore_to_netsuite_locations = {}
    _newstore_to_netsuite_payments = {}
    _dc_timezone_mapping = {}
    _newstore_to_netsuite_channels = {}

    @staticmethod
    def get_newstore_conn(context=None):
        if not Utils._newstore_conn:
            newstore_config = Utils._get_newstore_config()
            Utils._newstore_conn = NewStoreConnector(
                tenant=TENANT,
                context=context,
                host=newstore_config['host'],
                username=newstore_config['username'],
                password=newstore_config['password'],
                raise_errors=True
            )
        return Utils._newstore_conn

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
    def get_netsuite_config():
        if not Utils._netsuite_config:
            Utils._netsuite_config = json.loads(
                Utils._get_param_store().get_param('netsuite'))
        return Utils._netsuite_config

    @staticmethod
    def get_netsuite_location_map():
        if not Utils._newstore_to_netsuite_locations:
            location_params = json.loads(Utils._get_param_store().get_param(
                'netsuite/newstore_to_netsuite_locations'))
            Utils._newstore_to_netsuite_locations = location_params
        return Utils._newstore_to_netsuite_locations

    @staticmethod
    def get_nws_to_netsuite_payment():
        if not Utils._newstore_to_netsuite_payments:
            Utils._newstore_to_netsuite_payments = json.loads(
                Utils._get_param_store().get_param('netsuite/newstore_to_netsuite_payment_items')
            )
        return Utils._newstore_to_netsuite_payments

    @staticmethod
    def get_dc_timezone_mapping_config():
        if not Utils._dc_timezone_mapping:
            Utils._dc_timezone_mapping = json.loads(
                Utils._get_param_store().get_param('netsuite/dc_timezone_mapping').split(',')
            )
        return Utils._dc_timezone_mapping

    @staticmethod
    def get_nws_to_netsuite_channel():
        if not Utils._newstore_to_netsuite_channels:
            Utils._newstore_to_netsuite_channels = json.loads(
                Utils._get_param_store().get_param('netsuite/newstore_to_netsuite_channel')
            )
        return Utils._newstore_to_netsuite_channels

    @staticmethod
    def _get_netsuite_store_mapping(nws_value):
        if not nws_value:
            return {}

        locations_config = Utils.get_netsuite_location_map()
        mapping = locations_config.get(nws_value)
        if mapping is None:
            # try to get mapping for pre-pended code
            mapping = locations_config.get(nws_value[:3])

        if mapping is None:
            LOGGER.error(
                f'Failed to obtain newstore to netsuite location mapping for \'{nws_value}\'')
            return {}

        return mapping

    @staticmethod
    def get_netsuite_store_internal_id(nws_value, is_sellable=True):
        mapping = Utils._get_netsuite_store_mapping(nws_value)
        return mapping.get('id') if is_sellable else mapping.get('id_damage')

    @staticmethod
    def get_not_taxable_id(subsidiary_id):
        if int(subsidiary_id) == int(Utils.get_netsuite_config().get('subsidiary_us_internal_id')):
            return Utils.get_netsuite_config()['not_taxable_us']
        if int(subsidiary_id) == int(Utils.get_netsuite_config().get('subsidiary_ca_internal_id')):
            return Utils.get_netsuite_config()['not_taxable_ca']
        raise ValueError(f"Provided subsidary ID, {subsidiary_id}, not mapped")

    @staticmethod
    def is_endless_aisle(order_payload):
        return order_payload.get('channel_type', '') == 'store' and \
            order_payload['shipment_details'][0]['shipping_option']['shipping_type'] == 'traditional_carrier'

    @staticmethod
    def get_one_of_these_fields(params={}, fields=[]):
        return next((params[field] for field in fields if field in params), None)

    @staticmethod
    def get_currency_from_country_code(country_code):
        currency_map = {
            'US': int(Utils.get_netsuite_config()['currency_usd_internal_id']),
            'CA': int(Utils.get_netsuite_config()['currency_cad_internal_id']),
            'GB': int(Utils.get_netsuite_config()['currency_gbp_internal_id']),
            'EU': int(Utils.get_netsuite_config()['currency_eur_internal_id'])
        }
        return currency_map.get(str(country_code))

    @staticmethod
    def format_datestring_for_netsuite(date_string, time_zone, cutoff_index=19, format_string='%Y-%m-%dT%H:%M:%S'):
        time_zone = Utils.get_netsuite_config().get(
            'NETSUITE_DATE_TIMEZONE', 'America/New_York')
        tran_date = datetime.strptime(
            date_string[:cutoff_index], format_string)
        tran_date = tran_date.replace(tzinfo=timezone('UTC'))
        try:
            tran_date = tran_date.astimezone(timezone(time_zone))
        except UnknownTimeZoneError:
            LOGGER.warning(
                f'Invalid timezone {time_zone}, defaulting to America/New_York')
            tran_date = tran_date.astimezone(timezone('America/New_York'))
        return tran_date

    @staticmethod
    def replace_associate_id_for_email(customer_order):
        associate_id = customer_order['associate_id']
        if not associate_id:
            return
        employee = Utils.get_newstore_conn().get_employee(associate_id)
        if employee:
            customer_order['associate_id'] = employee['email']

    @staticmethod
    def get_countries():
        if not Utils._countries:
            filename = os.path.join(os.path.dirname(
                __file__), 'iso_country_codes.csv')
            with open(filename) as countries_file:
                file = csv.DictReader(countries_file, delimiter=',')
                for line in file:
                    Utils._countries[line['Alpha-2 code']] = Utils._format_country_name(
                        line['English short name lower case'])
        return Utils._countries

    @staticmethod
    def _format_country_name(country_name):
        def func(country_name):
            return country_name[:1].lower() + country_name[1:] if country_name else ''
        return '_'+func(country_name).replace(' ', '')

    @staticmethod
    def json_serial(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError("Type %s not serializable" % type(obj))
