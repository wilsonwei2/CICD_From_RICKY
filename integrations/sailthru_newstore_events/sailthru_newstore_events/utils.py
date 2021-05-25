from param_store.client import ParamStore
import os
import json

PARAM_STORE = None
# in order to use Param Store, the following env vars must be specified in the file importing utils.py:
TENANT = os.environ.get('TENANT')
STAGE = os.environ.get('STAGE')


def get_param(param_path):
    return json.loads(
        _get_parameter_store().get_param(param_path))


def _get_parameter_store(tenant: str = TENANT, stage: str = STAGE):
    global PARAM_STORE # pylint: disable=global-statement
    if not PARAM_STORE:
        PARAM_STORE = ParamStore(tenant, stage)
    return PARAM_STORE
