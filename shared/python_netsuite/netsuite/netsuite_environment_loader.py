import os
import json
import logging
from param_store.client import ParamStore


def get_netsuite_config():
    return json.loads(PARAM_STORE.get_param('netsuite'))

def get_creds_config():
    return json.loads(PARAM_STORE.get_param('netsuite_creds'))


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

LOGGER.debug('Setting up connection Parameter Store.')
TENANT = os.environ.get('TENANT')
STAGE = os.environ.get('STAGE')
PARAM_STORE = ParamStore(tenant=TENANT, stage=STAGE)

LOGGER.debug('Pulling startup environment data from Parameter Store.')
netsuite_config = get_netsuite_config()
creds_config = get_creds_config()

LOGGER.debug('Setting environment variables.')
os.environ['netsuite_synced_to_newstore_flag_internal_id'] = netsuite_config.get('synced_to_newstore_flag_internal_id', 'NOT_FOUND')
os.environ['netsuite_synced_to_newstore_flag_script_id'] = netsuite_config.get('synced_to_newstore_flag_script_id', 'NOT_FOUND')
os.environ['sales_order_rejection_synced_to_newstore_script_id'] = netsuite_config.get('sales_order_rejection_synced_to_newstore_script_id', 'NOT_FOUND')

# NetSuite Credentials environment variables
os.environ['netsuite_account_id'] = creds_config.get('account_id', 'NOT_FOUND')
os.environ['netsuite_application_id'] = creds_config.get('application_id', 'NOT_FOUND')
os.environ['netsuite_email'] = creds_config.get('email', 'NOT_FOUND')
os.environ['netsuite_password'] = creds_config.get('password', 'NOT_FOUND')
os.environ['netsuite_role_id'] = creds_config.get('role_id', 'NOT_FOUND')
os.environ['netsuite_wsdl_url'] = creds_config.get('wsdl_url', 'NOT_FOUND')

# Token Based Auth environment variables
os.environ['netsuite_tba_active'] = creds_config.get('activate_tba', '0')
os.environ['netsuite_disable_login'] = creds_config.get('disable_login', '0')
os.environ['netsuite_consumer_key'] = creds_config.get('consumer_key', 'NOT_FOUND')
os.environ['netsuite_consumer_secret'] = creds_config.get('consumer_secret', 'NOT_FOUND')
os.environ['netsuite_token_key'] = creds_config.get('token_key', 'NOT_FOUND')
os.environ['netsuite_token_secret'] = creds_config.get('token_secret', 'NOT_FOUND')

LOGGER.info('Netsuite environment loader finished successfully.')
