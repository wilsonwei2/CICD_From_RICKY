import os
import json
import boto3
import logging
from time import time
from datetime import datetime, date
from pytz import timezone
from pytz.exceptions import UnknownTimeZoneError
from param_store.client import ParamStore
from newstore_adapter.connector import NewStoreConnector
from boto3.dynamodb.conditions import Key
# import ptvsd
# ptvsd.enable_attach(address=('localhost', 65531), redirect_output=True)
# ptvsd.wait_for_attach()

LOGGER = logging.getLogger(__file__)
LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'info').upper() or 'INFO'
LOG_LEVEL = getattr(logging, LOG_LEVEL_SET, None)
if not isinstance(LOG_LEVEL, int):
    LOG_LEVEL = getattr(logging, 'INFO', None)
LOGGER.setLevel(LOG_LEVEL)
TENANT = os.environ.get('TENANT')
STAGE = os.environ.get('STAGE')
DAY_IN_SECONDS = 60*60*24
DYNAMO_SCAN_LIMIT = int(os.environ.get('DYNAMO_SCAN_LIMIT', 50))


class Utils():
    _param_store = None
    _dynamo_table = None
    _newstore_conn = None
    _newstore_to_netsuite_locations = {}

    @staticmethod
    def get_newstore_conn(context=None):
        if not Utils._newstore_conn:
            newstore_creds = Utils.get_newstore_config()
            Utils._newstore_conn = NewStoreConnector(tenant=newstore_creds['tenant'], context=context,
                                                     username=newstore_creds['username'],
                                                     password=newstore_creds['password'], host=newstore_creds['host'],
                                                     raise_errors=True)
        return Utils._newstore_conn

    @staticmethod
    def get_param_store():
        if not Utils._param_store:
            Utils._param_store = ParamStore(tenant=TENANT,
                                            stage=STAGE)
        return Utils._param_store

    @staticmethod
    def get_dynamo_table(table_name):
        LOGGER.info(f'Table name {table_name}')
        if not Utils._dynamo_table:
            Utils._dynamo_table = boto3.resource('dynamodb').Table(table_name)
        return Utils._dynamo_table

    @staticmethod
    def get_newstore_config():
        return json.loads(Utils.get_param_store().get_param('newstore'))

    @staticmethod
    def get_netsuite_config():
        return json.loads(Utils.get_param_store().get_param('netsuite'))

    @staticmethod
    def get_netsuite_location_map():
        if not Utils._newstore_to_netsuite_locations:
            location_params = json.loads(Utils.get_param_store().get_param(
                'netsuite/newstore_to_netsuite_locations'))
            Utils._newstore_to_netsuite_locations = location_params
        return Utils._newstore_to_netsuite_locations

    @staticmethod
    def get_store(store_id):
        store = Utils.get_newstore_conn().get_store(store_id)
        if store:
            return store
        raise ValueError(
            f'Unable to retrieve information from NewStore for store {store_id}')

    @staticmethod
    def get_product(product_id, catalog, locale):
        product = Utils.get_newstore_conn().get_product(product_id, catalog, locale)
        if product:
            return product
        raise ValueError(
            f'Unable to retrieve information from NewStore for product {product_id}')

    @staticmethod
    def json_serial(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError("Type %s not serializable" % type(obj))

    @staticmethod
    def get_netsuite_store_mapping(nws_value):
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
        mapping = Utils.get_netsuite_store_mapping(nws_value)
        return mapping.get('id') if is_sellable else mapping.get('id_damage')

    @staticmethod
    def get_one_of_these_fields(params, fields):
        if params is None:
            params = {}
        if fields is None:
            fields = []

        return next((params[field] for field in fields if field in params), None)

    @staticmethod
    def get_subsidiary_from_currency(currency_id):
        subsidiary_map = {
            int(Utils.get_netsuite_config()['currency_usd_internal_id']): int(Utils.get_netsuite_config()['subsidiary_us_internal_id']),
            int(Utils.get_netsuite_config()['currency_cad_internal_id']): int(Utils.get_netsuite_config()['subsidiary_ca_internal_id'])
        }
        return subsidiary_map.get(int(currency_id))

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
    def format_datestring_for_netsuite(date_string, time_zone, cutoff_index=22, format_string='%Y-%m-%dT%H:%M:%S.%f'):
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
    def get_nws_location_id(nws_store_fulfillment_node):
        store_config = Utils.get_netsuite_location_map()
        for location_id in store_config:
            if store_config[location_id]['ff_node_id'] == nws_store_fulfillment_node:
                return location_id
        return None

    @staticmethod
    def clear_old_events(dynamo_table, days):
        LOGGER.warning(f'Clearing event cache more than {days} days old')

        timestamp_threshold = int(time() - (days * DAY_IN_SECONDS))
        LOGGER.info(f"timestamp_threshold {timestamp_threshold}")
        response = dynamo_table.scan(
            FilterExpression=Key('timestamp').lt(timestamp_threshold))
        data = response['Items']
        LOGGER.info(f'Data {data}')

        while 'LastEvaluatedKey' in response:
            response = dynamo_table.scan(
                FilterExpression=Key('timestamp').lt(timestamp_threshold),
                ExclusiveStartKey=response['LastEvaluatedKey'])
            data.extend(response['Items'])

        LOGGER.info(f'Found {len(data)} results: {data}')

        for event_row in data:
            dynamo_table.delete_item(Key={'id': event_row['id']})

    @staticmethod
    def event_already_received(event_id, event_id_cache_table):
        response = event_id_cache_table.scan(
            FilterExpression=Key('id').eq(event_id),
            Limit=DYNAMO_SCAN_LIMIT)

        if response['Items']:
            return True

        while 'LastEvaluatedKey' in response:
            response = event_id_cache_table.scan(
                FilterExpression=Key('id').eq(event_id),
                Limit=DYNAMO_SCAN_LIMIT,
                ExclusiveStartKey=response['LastEvaluatedKey'])
            if response['Items']:
                return True
        return False

    @staticmethod
    def mark_event_as_received(event_id, event_id_cache_table):
        event_id_cache_table.put_item(
            Item={
                'id': event_id,
                'timestamp': int(time())
            },
            ConditionExpression='attribute_not_exists(id)'
        )

    @staticmethod
    def get_environment_variable(env_parameter_id, default_local_value):
        # Check how this environment variable works in prod. Maybe we can create a environment variable directly in the serverless.yml
        is_offline = os.environ.get("IS_OFFLINE")
        if is_offline:
            return default_local_value
        return os.environ.get(env_parameter_id)
