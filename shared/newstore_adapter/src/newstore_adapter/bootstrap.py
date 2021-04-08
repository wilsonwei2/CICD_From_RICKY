import uuid
import json
import logging
import requests

BOOTSTRAP_ENDPOINT = "_/v0/dontuse"
logger = logging.getLogger(__name__)


def get_store(ctx, store_id=None):
    """
    Get a store or all stores
    :param ctx: The context containing the url and auth
    :param store_id: the id to fecth an store, if None return all stores
    :return: a {} with a store or a [{}] with all stores
    """
    url = ''
    if store_id:
        url = ctx.api_url_v2(BOOTSTRAP_ENDPOINT, 'stores', store_id)
    else:
        url = ctx.api_url_v2(BOOTSTRAP_ENDPOINT, 'stores')
    response = requests.get(url, auth=ctx.auth)
    response.raise_for_status()
    return response.json()

def upsert_store(ctx, store_id, store_data):
    """
    Update or create a store by validating store_id already exists
    :param ctx: The context containing the url and auth
    :return: a list of exported items
    """
    url = ctx.api_url_v2(BOOTSTRAP_ENDPOINT, 'stores', store_id)
    response = requests.get(url, auth=ctx.auth)
    if response.status_code == requests.codes.ok:
        logger.info('Store exists; updating it....')
        response = requests.patch(url, json=store_data, auth=ctx.auth)
        response.raise_for_status()
        return response.json()
    else:
        logger.info('New store; creating it....')
        url = ctx.api_url_v2(BOOTSTRAP_ENDPOINT, 'stores')
        response = requests.post(url, json=store_data, auth=ctx.auth)
        response.raise_for_status()
        return response.json()


def get_employee(ctx, employee_id=None):
    """
    Get a employee or all employee
    :param ctx: The context containing the url and auth
    :param employee_id: the id to fecth an employee, if nNone return all employees
    :return: a {} with a employee or a [{}] with all empployees
    """
    url = ''
    if employee_id:
        url = ctx.api_url_v2(BOOTSTRAP_ENDPOINT, 'employee', employee_id)
    else:
        url = ctx.api_url_v2(BOOTSTRAP_ENDPOINT, 'employee')
    response = requests.get(url, auth=ctx.auth)
    response.raise_for_status()
    return response.json()

def upsert_employee(ctx, employee_id, employee_data):
    """
    Update or create an employee, validation is done by employee id
    :param ctx: The context containing the url and auth
    :return: a list of exported items
    """
    url = ctx.api_url_v2(BOOTSTRAP_ENDPOINT, 'employees', employee_id)
    response = requests.get(url, auth=ctx.auth)
    if response.status_code == requests.codes.ok:
        response = requests.patch(url, json=employee_data, auth=ctx.auth)
        response.raise_for_status()
        return response.json()
    else:
        url = ctx.api_url_v2(BOOTSTRAP_ENDPOINT, 'employees')
        response = requests.post(url, json=employee_data, auth=ctx.auth)
        response.raise_for_status()
        return response.json()


def upsert_fulfillment_config(ctx, fc_data):
    """
    Update or create the requested fulfillment configuration
    :param ctx: The context containing the url and auth
    :return: a list of exported items
    """
    url = ctx.api_url_v2(BOOTSTRAP_ENDPOINT, 'fulfillment_config')
    response = requests.post(url, json=fc_data, auth=ctx.auth)
    response.raise_for_status()
    return response.json()
