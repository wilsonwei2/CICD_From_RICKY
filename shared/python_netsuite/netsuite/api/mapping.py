import json
import os
import logging

from param_store.client import ParamStore
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel('INFO')


class NetSuiteMapping():
    PARAM_STORE = None
    NETSUITE_CONFIG = None

    def _get_param_store(self):
        if not self.PARAM_STORE:
            tenant = os.environ.get('TENANT')
            stage = os.environ.get('STAGE')
            PARAM_STORE = ParamStore(tenant=tenant, stage=stage)
        return PARAM_STORE

    def _get_netsuite_config(self):
        NETSUITE_CONFIG = json.loads(
            self._get_param_store().get_param('netsuite'))
        return NETSUITE_CONFIG

    def get_currency_code(self, currency_id):
        currency_map = {
            str(self._get_netsuite_config()['currency_usd_internal_id']): 'USD',
            str(self._get_netsuite_config()['currency_cad_internal_id']): 'CAD',
            str(self._get_netsuite_config()['currency_gbp_internal_id']): 'GBP',
            str(self._get_netsuite_config()['currency_eur_internal_id']): 'EUR'
        }
        return currency_map.get(str(currency_id))
