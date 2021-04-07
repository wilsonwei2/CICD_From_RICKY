import os
from typing import List
import logging

logger = logging.getLogger(__name__)

INTEGRATION_ROOT = "integrations"


def get_integration_folder_name():
    return INTEGRATION_ROOT


def get_base_dir():
    key = "CIRCLE_WORKING_DIRECTORY"
    if key not in os.environ:
        root = os.path.abspath(os.sep)
        return os.path.join(root, "project")
    return os.path.expanduser(os.environ[key])


def get_integration_path():
    return os.path.join(get_base_dir(), INTEGRATION_ROOT)


def get_integration_dir(integration):
    return os.path.join(get_integration_path(), integration)

def get_make_file_path(integration):
    return os.path.join(get_integration_dir(integration), "Makefile")


def has_make_file(integration):
    return os.path.isfile(get_make_file_path(integration))


def log_diffs(diffs: List):
    for diff in diffs:
        logger.info(diff)
