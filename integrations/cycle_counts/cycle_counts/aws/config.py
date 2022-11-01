import os
import json
from typing import List
from dacite import from_dict

import netsuite.netsuite_environment_loader  # pylint: disable=W0611
from param_store.client import ParamStore

from cycle_counts.app.netsuite_newstore_service import NetSuiteNewStoreService
from cycle_counts.infrastructure.ItemIdsStore import ItemIdsStore
from cycle_counts.infrastructure.netsuite_client.client import NetSuiteCredentials, NetSuiteClient
from cycle_counts.infrastructure.netsuite_client_interface import NetSuiteClientInterface
from cycle_counts.infrastructure.netsuite_mock_client import NetSuiteMockClient
from cycle_counts.models.locations import Locations

PARAM_STORE = None
NEWSTORE_CONFIG = None
NETSUITE_CONFIG = None


def get_lambda_parameters() -> {}:
    environment_variables = {key.lower(): os.environ[key] for key in [
        'TENANT',
        'STAGE',
    ]}

    newstore_config = get_newstore_config()

    return {
        **environment_variables,
        'ns_user': newstore_config['username'],
        'ns_password': newstore_config['password'],
        'ns_tenant': newstore_config['tenant']
    }


def get_netsuite_client() -> NetSuiteClientInterface:
    if os.environ.get('MOCK_CLIENT', False):
        return NetSuiteMockClient()

    credentials = NetSuiteCredentials(
        account_id=os.environ.get('netsuite_account_id'),
        consumer_key=os.environ.get('netsuite_consumer_key'),
        consumer_secret=os.environ.get('netsuite_consumer_secret'),
        token_secret=os.environ.get('netsuite_token_secret'),
        token_key=os.environ.get('netsuite_token_key')
    )

    netsuite_config = get_netsuite_config()

    return NetSuiteClient(credentials=credentials, url=netsuite_config['cycle_count_restlet_endpoint'])


def get_newstore_netsuite_locations() -> List[Locations]:
    locations = []
    # TODO: Change that the mapping is read from a json file - should come from Param Store | pylint: disable=fixme
    # and maybe one of the existing mappings -> to be investigated
    # Note that I already cleaned the file and object type
    with open(os.path.join(os.path.dirname(__file__), '../json/stores_location_map.json')) as json_file:
        for location in json.load(json_file).values():
            location['netsuite_location_id'] = location.pop('id')
            locations.append(from_dict(data=location, data_class=Locations))

    return locations


def get_netsuite_newstore_service() -> NetSuiteNewStoreService:
    return NetSuiteNewStoreService(locations=get_newstore_netsuite_locations(), item_ids_store=get_item_ids_store())


def get_queue_name() -> str:
    return os.environ.get('CYCLE_COUNTS_QUEUE')


def get_eventstream_api_key() -> str:
    netsuite_config = get_netsuite_config()
    return netsuite_config['cycle_count_eventstream_api_key']


def get_item_ids_store() -> ItemIdsStore:
    return ItemIdsStore(os.environ.get('TABLE_NAME'))


def get_param_store():
    global PARAM_STORE  # pylint: disable=W0603
    if not PARAM_STORE:
        tenant = os.environ.get('TENANT')
        stage = os.environ.get('STAGE')
        PARAM_STORE = ParamStore(tenant=tenant, stage=stage)
    return PARAM_STORE


def get_newstore_config():
    global NEWSTORE_CONFIG  # pylint: disable=W0603
    if not NEWSTORE_CONFIG:
        NEWSTORE_CONFIG = json.loads(get_param_store().get_param('newstore'))
    return NEWSTORE_CONFIG


def get_netsuite_config():
    global NETSUITE_CONFIG  # pylint: disable=W0603
    if not NETSUITE_CONFIG:
        NETSUITE_CONFIG = json.loads(get_param_store().get_param('netsuite'))
    return NETSUITE_CONFIG
