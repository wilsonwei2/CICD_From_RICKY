import boto3
import logging

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class ParamStore():
    """Simple interface to SSM Param Store.

    Usage:
        ```
        from param_store.client import ParamStore

        TENANT = 'aninebing'
        STAGE = 'x'
        param_store = ParamStore(TENANT, STAGE)
        single_param = param_store.get_param('shopify/us')
        multiple_params = param_store.get_params_by_path('shopify')
        ```
    """

    def __init__(self, tenant, stage):
        """Initialize the module.
        By creating a new instance of the boto3 session client for accessing SSM
        Param Store. Also use a root path for all calls to tie access to a single
        tenant + stage.

        NOTE: To use this module, ensure that your parameters are configured
        properly in SSM. The convention of this module is the to expect params in
        the format `/tenant-name/stage-symbol/param-name` such that all params for
        Anine Bing sandbox (for example) would have a root path of `/aninebing/x/`
        and its params would be named something like `/aninebing/x/shopify`.

        Args:
            tenant: Name of Newstore tenant (e.g., "aninebing").
            stage: One-letter symbol representing the stage (e.g., "x", or "s" or "p").
            region: AWS region code where the SSM Param Store is configured.
                Defaults to `us-east-1`.

        Returns:
            New instance of ParamStore.
        """
        self.tenant = tenant
        self.stage = stage
        self.client = boto3.client('ssm')
        self.path_root = '/%s/%s/' % (tenant, stage)

    def get_client(self):
        return self.client

    def get_path_root(self):
        return self.path_root

    def get_tenant(self):
        return self.tenant

    def get_stage(self):
        return self.stage

    def get_param(self, key=''):
        """Get a single parameter value from the SSM Param Store.
        It uses a root path based on the values used to initialize the module.

        Args:
            key: Name of the parameter to get (not including the root path).

        Returns:
            value: The value of the parameter matching `key` or None if no match.
        """
        path = self.path_root + key
        response = None

        try:
            response = self.client.get_parameter(
                Name=path, WithDecryption=False)
            return response['Parameter']['Value']
        except Exception:
            LOGGER.exception(f'Error when trying to get parameter {path}')
            return None

    def get_params_by_path(self, input_path=''):
        """Get multiple parameters from the SSM Param Store.
        Returns an array of parameter dicts which contain a `name` and a `value` attribute;
        the `value` attribute being parsed as JSON and formatted as a dict itself.

        Args:
            path: A string indicating the base path from which to retrieve values.
                The `self.path_root` will be prepended to this path. To retrieve all
                values for a tenant, use an empty string for the value of `path`.

        Returns:
            parameters: An array of key/value pair dicts representing all params that
                match the `path` that was provided or an empty array if no matches.
        """
        def param_to_dict_minus_prefix(plen=0):
            """Return a dict containing two attributes: key + value.
            """
            def param_to_dict(param):
                return {
                    "key": param['Name'][plen:],
                    "value": param['Value']
                }

            return param_to_dict
        path = self.path_root + input_path
        prefix_len = len(self.path_root)
        has_next_token = True
        next_token = None
        parameters = []

        while has_next_token:
            response = None

            if next_token == None:
                # Initial parameter request (without `NextToken`).
                response = self.client.get_parameters_by_path(
                    Path=path,
                    Recursive=False,
                    WithDecryption=False,
                    MaxResults=3
                )
            else:
                # If next_token has a value the continue requesting from server
                # to retrieve remaining parameters.
                response = self.client.get_parameters_by_path(
                    Path=path,
                    Recursive=False,
                    WithDecryption=False,
                    MaxResults=3,
                    NextToken=next_token
                )

            # Append all retrieved parameters to the `parameters` list, formatted
            # as dicts with `key`/`value` pairs.
            parameters += list(map(param_to_dict_minus_prefix(prefix_len),
                                   response['Parameters']))

            # If there's a `NextToken` in the response, then continue requesting
            # more params, otherwise stop the loop.
            if 'NextToken' in response:
                next_token = response['NextToken']
            else:
                has_next_token = False

        return parameters
