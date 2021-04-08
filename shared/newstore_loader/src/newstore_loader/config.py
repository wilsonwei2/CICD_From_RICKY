# Copyright (C) 2017 NewStore Inc, all rights reserved.

"""
Bootstrap configuration.

Copyright (C) 2017 NewStore, Inc. All rights reserved.
"""

import logging
import os
import sys
import yaml

import newstore_adapter
from newstore_loader import json_stream
import requests

LOGGER = logging.getLogger(__name__)

# stop connection pool from being chatty -- sorry!
logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.WARNING)

DEFAULT_TENANT = os.environ.get("BOOTSTRAP_TENANT", "dodici")
DEFAULT_STAGE = os.environ.get("BOOTSTRAP_STAGE", "l")


def main_function(func):
    """
    Execute main function `func` for each filename parameter in turn. Parameters are:
    1. Config class instance
    2. Filename as a string
    """
    if len(sys.argv) > 1:
        cfg = Config()
        for filename in sys.argv[1::]:
            func(cfg, filename)


def read_yaml(filename):
    """
    Read a YAML file, yielding its records as a generator.
    """
    with open(filename) as fin:
        for data in yaml.load_all(fin):
            yield data


def tenant_root():
    """
    Return the folder path name containing tenants.
    """
    folder = None
    parent = os.environ.get("TENANT_ROOT", os.getcwd())
    while folder != parent:
        folder = parent
        filename = os.path.join(folder, "stages.yaml")
        if os.path.exists(filename):
            return folder
        parent = os.path.join(os.path.dirname(folder), "tenants")


class Config(object):

    """
    Configuration object governing all loader functions.
    """

    def __init__(self, tenant=DEFAULT_TENANT, stage=DEFAULT_STAGE):
        self.ctx = newstore_adapter.Context(tenant, stage)

        for data in self.read_file("tenant.yaml"):
            self.__tenant_config__ = data
            break

        for data in self.read_file("../../../private/%s-admin.yaml" % tenant):
            self.ctx.set_user(data["username"], data["password"])
            break

    def read_file(self, filename, quiet=False):
        """
        Read one input file, allowing YAML or JSON format.
        """
        filename = os.path.join(tenant_root(), self.ctx.tenant, "bootstrap", filename)
        if not quiet:
            LOGGER.debug("Reading file: %s\n", filename)
        if filename.endswith(('.yaml', '.yml')):
            return read_yaml(filename)
        if filename.endswith(('.json', '.js')):
            return json_stream.read_json(filename)
        raise NotImplementedError(filename)


    def tenant_property(self, key):
        """
        Get a property from tenant configuration.
        """
        return self.__tenant_config__[key]
