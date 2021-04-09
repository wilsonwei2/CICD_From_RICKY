import os
import json
import base64
import logging
import requests
from string import Template
from shopify_import_products.shopify.param_store_config import ParamStoreConfig

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

SHOPIFY_HOST = os.environ.get('SHOPIFY_HOST') or 'myshopify.com/admin'
TENANT = os.environ.get('TENANT') or 'frankandoak'
STAGE = os.environ.get('STAGE') or 'x'
SHOPIFY_API_VERSION = os.environ.get('SHOPIFY_API_VERSION') or '2021-04'
PARAM_CONFIGS = ParamStoreConfig(TENANT, STAGE)


def _get_param_store():
    return PARAM_CONFIGS.get_param_store()


def get_shopify_config():
    return PARAM_CONFIGS.get_shopify_config()


def get_products(json_params, next_page=None):
    ## Function that is used to fetch products from shopify.
    shopify_config = get_shopify_config()
    shop = shopify_config['shop']
    username = shopify_config['username']
    password = shopify_config['password']

    if next_page:
        url = next_page
        response = requests.get(url, auth=(username, password))
    else:
        url = f'https://{shop}.{SHOPIFY_HOST}/api/{SHOPIFY_API_VERSION}/products.json'
        response = requests.get(url, auth=(username, password), params=json_params)

    try:
        response.raise_for_status()
    except requests.HTTPError as ex:
        LOGGER.exception(response.text)
        LOGGER.exception(ex)
        raise ex

    response_json = response.json()
    LOGGER.debug(f"Products: \n{json.dumps(response_json['products'], indent=4)}")
    LOGGER.info(f'Headers: {response.headers}')

    links = response.headers.get('Link', '').split(',')
    next_page = ''
    last_page = ''
    for link in links:
        if link and len(link.split(';')) > 1:
            if 'previous' in link.split(';')[1]:
                last_page = link.split(';')[0].strip()[1:-1]
            elif 'next' in link.split(';')[1]:
                next_page = link.split(';')[0].strip()[1:-1]

    return response_json['products'], last_page, next_page


def get_metafields(product_id):
    ## Extracting product information.
    ## 1. images
    ## 2. brim_category
    ## 3. mfg_
    ## 4. Crown_type
    ## 5. crown_dimension
    shopify_config = get_shopify_config()
    shop = shopify_config['shop']
    username = shopify_config['username']
    password = shopify_config['password']

    url = f'https://{shop}.{SHOPIFY_HOST}/api/{SHOPIFY_API_VERSION}/products/{product_id}/metafields.json'

    auth_string = ('{key}:{pwd}'.format(key=username, pwd=password))

    auth_header = {
        'Content-Type': 'application/json ',
        'Authorization': 'Basic {auth_base64}'.format(
            auth_base64=base64.b64encode(
                auth_string.encode()).decode('utf-8')
        )
    }

    response = requests.get(url, headers=(auth_header))

    try:
        response.raise_for_status()
    except requests.HTTPError as ex:
        LOGGER.exception(response.text)
        LOGGER.exception(ex)
        raise ex

    if response.json()['metafields']:
        return response.json()['metafields']

    return []


def get_variant_metafields(product_id, variant_id):
    '''
        This is the function that is used for fetching to variant
    '''
    shopify_config = get_shopify_config()
    shop = shopify_config['shop']
    username = shopify_config['username']
    password = shopify_config['password']

    url = f'https://{shop}.{SHOPIFY_HOST}/api/{SHOPIFY_API_VERSION}/'\
          f'products/{product_id}/variants/{variant_id}/metafields.json?key=netsuite_internal_id'

    auth_string = ('{key}:{pwd}'.format(key=username, pwd=password))

    auth_header = {
        'Content-Type': 'application/json ',
        'Authorization': 'Basic {auth_base64}'.format(
            auth_base64=base64.b64encode(
                auth_string.encode()).decode('utf-8')
        )
    }

    response = requests.get(url, headers=(auth_header))

    try:
        response.raise_for_status()
    except requests.HTTPError as ex:
        LOGGER.exception(response.text)
        LOGGER.exception(ex)
        raise ex

    if response.json()['metafields']:
        return response.json()['metafields']
    return []


def get_product_collection(product_id):
    '''
        We use product ID and fetch all the corresponding collections using the graphQL API of shopify.
    '''
    shopify_config = get_shopify_config()
    shop = shopify_config['shop']
    username = shopify_config['username']
    password = shopify_config['password']

    query_template = Template("""
    {
      product(id: "gid://shopify/Product/$product_id") {
          collections(first: 20) {
            edges {
              node {
                title
              }
            }
          }
      }
    }
    """)

    query = query_template.substitute(product_id=product_id)

    auth_string = ('{key}:{pwd}'.format(key=username, pwd=password))

    auth_header = {
        'Content-Type': 'application/json ',
        'Authorization': 'Basic {auth_base64}'.format(
            auth_base64=base64.b64encode(
                auth_string.encode()).decode('utf-8')
        )
    }

    url = f'https://{shop}.{SHOPIFY_HOST}/api/{SHOPIFY_API_VERSION}/graphql.json'

    response = requests.post(url, headers=(auth_header), json={'query': query})

    return response.json()
