# Copyright (C) 2015, 2016 NewStore, Inc. All rights reserved.
import logging

logger = logging.getLogger(__name__)

schema = {
    "properties": {
        "stages": {
            "mergeStrategy": "objectMerge"
        }
    }
}


def get_env_variables(function_name, isversion=None, version=None):
    import boto3
    client = boto3.client('lambda')
    configuration = client.get_function_configuration(FunctionName=function_name)
    return configuration.get("Environment", {}).get("Variables", {})


def merge_config_files(super_json, sub_json):
    from jsonmerge import Merger
    merger = Merger(schema)
    env_vars = merger.merge(super_json, sub_json)
    return env_vars


def update_env_variables(new_config, function_name):
    import boto3
    client = boto3.client("lambda")

    response = client.update_function_configuration(
        FunctionName=function_name,
        Environment={
            'Variables': new_config
        },
    )
    logger.info("Lambda Env variables updated")
