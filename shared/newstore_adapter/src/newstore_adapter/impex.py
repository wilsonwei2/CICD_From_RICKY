# -*- coding: utf-8 -*-

"""
Import and export adapter utilities.

Copyright (C) 2017 NewStore, Inc. All rights reserved.
"""


import uuid
import json
import logging
import requests
from . import transformer

IMPORT_ENDPOINT = "d/import"
EXPORT_ENDPOINT = "d/export"
CONSUMER_PRICES = "c/prices"
CONSUMER_PRODUCTS = "c/products"
CONSUMER_ORDERS = 'c/consumers'
HQ_ORDERS = "hq/customer_orders"
OPEN_DELIVERIES = 'd/open_deliveries'
DELIVERY_STATUS = 'd/delivery_status'

logger = logging.getLogger(__name__)


class Job(object):

    """ Representation of a job that is managed by the import manager in core environment """

    _S3_URL_FORMAT = 's3://{}/{}'

    def __init__(self, ctx):
        self.ctx = ctx
        self.import_id = None
        self.meta_info = None

    @classmethod
    def s3_url(cls, s3object):
        """ Return a URL of the form `s3://<bucket-name>/<object-key>` """
        return cls._S3_URL_FORMAT.format(s3object.bucket_name, s3object.key)

    @property
    def source_uri(self):
        """ The source URI that was provided on job creation. """
        return self.meta_info['source_uri']

    @property
    def import_type(self):
        """ The import type that was provided on job creation. """
        return self.meta_info['type']

    def create(self, meta):
        """
        Actually create this job at the import API. meta must be a dictionary of:

            meta = {
                'provider': 'dodici-samples',
                'name': 'initialization repository',
                'source_uri': 's3://some-bucket-name/and/object/key',
                'revision': 0,
                'entities': ['categories','products'],
                'full': True
            }

        Entities may be: 'products', 'categories', 'availabilities', 'prices', 'dwre_orders'
        The source URI specifies the location of the initial, untransformed input.
        """
        url = self.ctx.api_url(IMPORT_ENDPOINT)
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, auth=self.ctx.auth, data=json.dumps(meta))
        logger.info(response.text)
        response.raise_for_status()
        self.import_id = response.json()['id']
        self.meta_info = meta
        return self  # allow job = Job(ctx, auth).create(meta)

    def error(self, reason, error_id=None, entity_type=None, entity_id=None):
        """
        Store an error that occurred in the context of this import job.
        """
        if error_id is None:
            error_id = str(uuid.uuid4())
        if entity_type is None:
            entity_type = ''
        if entity_id is None:
            entity_id = ''
        meta = [{
            'reason': reason,
            'error_id': error_id,
            'entity_type': entity_type,
            'entity_id': entity_id
        }]
        headers = {'Content-Type': 'application/json'}
        url = self.ctx.api_url(IMPORT_ENDPOINT, self.import_id, 'errors')
        response = requests.post(url, headers=headers, auth=self.ctx.auth, data=json.dumps(meta))
        response.raise_for_status()
        return {'response_code': response.status_code, 'response': json.dumps(response.json())}

    def failed(self, reason):
        """
        Mark this import job as failed.
        """
        meta = {'reason': reason}
        headers = {'Content-Type': 'application/json'}
        url = self.ctx.api_url(IMPORT_ENDPOINT, self.import_id, 'set_fail')
        response = requests.post(url, headers=headers, auth=self.ctx.auth, data=json.dumps(meta))
        response.raise_for_status()
        return {'response_code': response.status_code, 'response': response.json()}

    def start(self, transformed_uri):
        """
        Start importing for this job. The transformed_uri specifies the location in S3
        where the transformed file to import is to be found.
        """
        meta = {'transformed_uri': transformed_uri}
        headers = {'Content-Type': 'application/json'}
        url = self.ctx.api_url(IMPORT_ENDPOINT, self.import_id, 'start')
        response = requests.post(url, headers=headers, auth=self.ctx.auth, data=json.dumps(meta))
        response.raise_for_status()
        return {'response_code': response.status_code, 'response': response.json()}

    def transform(self):
        """ Hand off this job to the transformer. Job has to be started already. """
        return transformer.post(self.ctx, self)

    def errors(self):
        """
        Retrieve the error messages of this import job.
        """
        url = self.ctx.api_url(IMPORT_ENDPOINT, self.import_id, 'errors')
        response = requests.get(url, auth=self.ctx.auth)
        response.raise_for_status()
        return {'response_code': response.status_code, 'response': response.json()}

    def status(self):
        """
        Retrieve the status of this import job.
        """
        url = self.ctx.api_url(IMPORT_ENDPOINT, self.import_id)
        response = requests.get(url, auth=self.ctx.auth)
        response.raise_for_status()
        return {'response_code': response.status_code, 'response': response.json()}

    @classmethod
    def list(cls, ctx):
        """
        List known jobs.
        """
        url = ctx.api_url(IMPORT_ENDPOINT)
        response = requests.get(url, auth=ctx.auth)
        response.raise_for_status()
        return {'response_code': response.status_code, 'response': response.json()}


IMPORT_AVAILABILITY = 'availability'


def availability_export(ctx):
    """
    Get's the availability export list
    :param ctx: The context containing the url and auth
    :return: a list of exported items
    """
    url = ctx.api_url(EXPORT_ENDPOINT, 'availabilities')
    response = requests.get(url, auth=ctx.auth)
    response.raise_for_status()
    return response.json()


def availability_import(ctx, availabilities):
    """
    Import a new availabilities list of products
    :param ctx:
    :param availabilities:
    :return:
    """
    url = ctx.api_url(IMPORT_ENDPOINT, IMPORT_AVAILABILITY)
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers=headers, auth=ctx.auth, json=availabilities)
    response.raise_for_status()
    return response.json()


def financial_transaction_list(ctx, params=None, limit=None):
    """
    Returns a dictionary containing the export reference id and the orders for each one
    Currently the financial api separates by 50 orders by reference id
    :param ctx: The context containing the url and auth
    :param params: the params to call finance api
    :return: a dic in the format {'{external_ref_id_1}': [{order_list_1}], '{external_ref_id_2}': [{order_list_2}]}
    """
    url = ctx.api_url(EXPORT_ENDPOINT, 'financial_transactions')
    result = {}
    page = 0
    while True:
        if limit and page == limit:
            return result
        page += 1
        response = requests.get(url, auth=ctx.auth, params=params)
        response.raise_for_status()
        json_response = response.json()
        if json_response.get('pagination_info', {}).get('total', 0) == 0:
            logging.warning('No orders found for today %s', json_response)
            return result

        # Loop through pages
        logging.info(
            'Processing page %s containing %s records out of %s total...',
            page,
            json_response.get('pagination_info', {}).get('count'),
            json_response.get('pagination_info', {}).get('total')
        )
        export_reference_id = json_response['meta']['export_reference_id']
        result.update({export_reference_id: json_response['items']})

        if response.json().get('pagination_info', {}).get('next_url', None) is None:
            return result
        else:
            params = response.json()['pagination_info']['next_url'].split('?')[1]


def get_price(ctx, params):
    """
    Get the price of a item from the consumer API
    :param ctx: The context containing the url and auth
    :param params: the params to pass in the call
    :return: the json parsed response
    """
    url = ctx.api_url(CONSUMER_PRICES)
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def get_products(ctx, sku, params):
    """
    Get the product by sku from the consumer API
    :param ctx: The context containing the url and auth
    :param sku: the sku of the product
    :param params: the params to pass in the call
    :return: the json [arsed response
    """
    url = ctx.api_url(CONSUMER_PRODUCTS, sku)
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def get_consumer_orders(ctx, consumer_id, params):
    """
    Get the consumer orders by consumer_id from the consumer API
    :param ctx: The context containing the url and auth
    :param sku: the sku of the product
    :param params: the params to pass in the call
    :return: the json [arsed response
    """
    url = ctx.api_url(CONSUMER_ORDERS, consumer_id, 'orders')
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def get_hq_order_number(ctx, params):
    """
    :param ctx:
    :param params:
    :return:
    """
    url = ctx.hq_url(HQ_ORDERS)
    response = requests.get(url, auth=ctx.auth, params=params)
    response.raise_for_status()
    return response.json()['pagination_info']['total']


def get_open_deliveries(ctx, params):
    """
    :param ctx:
    :param params:
    :return:
    """
    url = ctx.api_url(OPEN_DELIVERIES)
    response = requests.get(url, auth=ctx.auth, params=params)
    response.raise_for_status()
    return response.json()['deliveries']


def update_delivery_status(ctx, delivery_id, data):
    """
    :param ctx:
    :param data:
    :return:
    """
    url = '%s/%s' % (ctx.api_url(DELIVERY_STATUS), delivery_id)
    headers = {
        'content-type': 'application/json',
        'cache-control': 'no-cache'
    }
    response = requests.post(url, headers=headers, auth=ctx.auth, data=json.dumps(data))
    response.raise_for_status()
