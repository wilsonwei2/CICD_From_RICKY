import os
import json
import logging
# Libs from shared
from lambda_utils.sqs.SqsHandler import SqsHandler
# Local
from shopify_import_products.shopify.products import (
    get_metafields
)
from shopify_import_products.dynamodb import (
    get_dynamodb_resource,
    insert_product_variant_data
)
from shopify_import_products.transformers.constants import (
    TAG_RE,
    INVENTORY_QUEUE_NAME as QUEUE_NAME,
    CATEGORIES
)

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)


def transform_products(products):
    category_builder = {}
    transformed_products = {
        "head": {
            "locale": "en-US",
            "shop": "storefront-catalog-en",
            "is_master": True
        },
        "items": transform_product_items(products, category_builder)
    }
    transformed_categories = {
        "head": {
            "locale": "en-US",
            "catalog": "storefront-catalog-en"
        },
        "items": [
            {
                "path": "All"
            }
        ]
    }
    transformed_categories['items'] += [
        {
            "path": category['path'],
            "is_main": category['is_main']
        } for category in category_builder.values()
    ]

    return transformed_products, transformed_categories


def transform_product_items(products, category_builder):
    dynamo_db = get_dynamodb_resource()
    items = []
    for product in products:
        ##Getting the category details
        # We may still need to get categories from colletions in the future, so leave it for now
        #product_collection = get_product_collection(product['id'])
        #collection = product_collection['data']['product']['collections']
        for variant in product['variants']:
            item = transform_item(product, variant, dynamo_db)
            if item:
                ## Category Allocation.
                #product_categories, category_builder = build_categ_from_collections(collection, category_builder)
                product_categories, category_builder = build_categ_from_tags(product['tags'], category_builder)
                item['categories'] = product_categories
                items.append(item)
    return items


def transform_item(product, variant, dynamo_db): # pylint: disable=W0613
    # Adding products only if the variant is a product (Not a gift card)
    if variant.get('sku', '') != '' and variant['sku'] not in ['Gift Card', 'gift_card_sku']:
        ## Step 1
        ## This is where the item is created and the all the common attributed are extracted first
        ## from product.json
        item = _load_json_file('product.json')
        ## Replacing it from the variant call.
        item['product_id'] = variant['sku']
        item['variant_group_id'] = str(product['id'])
        item['title'] = str(product.get('title', ''))
        item['brand'] = product['vendor']
        item['caption'] = str(product.get('title', ''))
        item['description'] = _remove_tags(_get_non_null_field(product, 'body_html', ''))
        item["keywords"] = product.get('tags', '').split(', ')
        item["shipping_weight_unit"] = variant['weight_unit'] if _get_non_null_field(variant, 'weight', '') else 'lb'
        item["shipping_weight_value"] = _get_non_null_field(variant, 'weight', '') or 2
        item["variation_color_value"] = _get_non_null_field(variant, 'option2', '')
        item["variation_size_value"] = _get_non_null_field(variant, 'option1', '')
        item['tax_class_id'] = variant['tax_code'] ## ML-224
        item['shipping_dimension_unit'] = "cm"
        item['images'] = transform_images(product, variant)

        if variant.get('sku'):
            item['external_identifiers'].append({
                "type": "sku",
                "value": variant['sku']
            })

        if variant.get('inventory_item_id'):
            item['external_identifiers'].append({
                "type": "shopify_inventory_item_id",
                "value": str(variant.get('inventory_item_id', ''))
            })

        if variant.get('barcode'):
            item['external_identifiers'].append({
                "type": "upc",
                "value": variant['barcode']
            })
            item['external_identifiers'].append({
                "type": "isbn",
                "value": variant['barcode']
            })
            item['external_identifiers'].append({
                "type": "ean13",
                "value": variant['barcode']
            })

        # Only append values to extended attributes if those values exists
        _append_if_exists(item["extended_attributes"], product.get('created_at', ''), 'product_created_at')
        _append_if_exists(item["extended_attributes"], variant.get('created_at', ''), 'variant_created_at')
        _append_if_exists(item["extended_attributes"], product.get('updated_at', ''), 'product_updated_at')
        _append_if_exists(item["extended_attributes"], variant.get('updated_at', ''), 'variant_updated_at')
        _append_if_exists(item["extended_attributes"], product.get('handle', ''), 'product_handle')
        _append_if_exists(item["extended_attributes"], product.get('published_at', ''), 'product_published_at')
        _append_if_exists(item["extended_attributes"], product.get('published_scope', ''),
                          'product_published_scope')
        _append_if_exists(item["extended_attributes"], variant.get('fulfillment_service', ''),
                          'fulfillment_service')
        _append_if_exists(item["extended_attributes"], variant.get('inventory_item_id', ''),
                          'inventory_item_id')
        _append_if_exists(item["extended_attributes"], variant.get('inventory_management', ''),
                          'inventory_management')
        _append_if_exists(item["extended_attributes"], variant.get('inventory_policy', ''),
                          'inventory_policy')
        _append_if_exists(item["extended_attributes"], variant.get('id', ''),
                          'shopify_variant_id')

        return format_with_metafields(item)
    return None


def transform_images(product, variant):
    images = [
        {
            "url": os.environ['url_image_placeholder'],
            "is_main": True,
        }
    ]

    if product['image']:
        images = [
            {
                "url": product['image']['src'],
                "is_main": True,
                "alt_text": product['image']['alt'] if product['image']['alt'] else ''
            }
        ]

    for image in product.get('images') or []:
        # Avoid append main image again
        if image['src'] != product.get('image', {}).get('src' ''):
            images.append({
                "url": image['src'],
                "alt_text": image['alt'],
                "is_color_swatch": variant.get('image_id', '') == image['id']
            })

    return images


def build_categ_from_tags(tags, category_builder):
    product_categories = [{
        "path": "All"
    }]

    tags = [tag.strip().lower() for tag in tags.split(',')]
    if tags:
        for main_category in CATEGORIES:
            if main_category in tags:
                build_categ(tags, main_category, product_categories, category_builder)
    return product_categories, category_builder


def build_categ(tags, main_category, product_categories, category_builder):
    path = f"All > {main_category.capitalize()}"
    product_categories.append({
        "path": path,
        "is_main": True
    })

    if path not in category_builder:
        category_builder[path] = {
            'path': path,
            'is_main': True
        }

    for sub_category in CATEGORIES[main_category]:
        if sub_category in tags:
            path = f"All > {main_category.capitalize()} > {CATEGORIES[main_category][sub_category]}"
            product_categories.append({
                "path": path
            })

            if path not in category_builder:
                category_builder[path] = {
                    'path': path,
                    'is_main': False
                }


def build_categ_from_collections(product_collections, category_builder):
    product_categories = [{
        "path": "All"
    }]

    collections = _get_non_null_field(product_collections, 'edges', {})

    if collections:
        first_collection = True
        for collection_node in collections:
            collection = str(collection_node['node']['title'])
            if first_collection:
                product_categories.append({
                    "path": f"All > {collection}",
                    "is_main": True
                })
                first_collection = False
            else:
                product_categories.append({
                    "path": f"All > {collection}"
                })
            category_title = str(collection.replace(' ', '')).lower()
            if not category_title in category_builder:
                category_builder[category_title] = collection
    return product_categories, category_builder


def format_with_metafields(product):
    '''
    Function used to extract metafields data, if there is no metafield data. -- we skip this product.

    Assumption:
    This integration works under an assumption that we have data that could be parsible in shopify metafields.
    If it doesn't work as expected -- we are going to skip it.
    '''
    product_id = product['variant_group_id']
    metafields = get_metafields(product_id)
    for field in metafields:
        if field.get('namespace', '') == 'product':
            ## This is the string value that is expected to be inserted and right format to be
            ## Converted to JSON.
            value = json.loads(field.get('value', '{}'))

            mfg = value.get("mfg", {})
            if "factory_code" in mfg:
                _append_if_exists(product["extended_attributes"], mfg["factory_code"], "mfg_factory_code")
            if "origin" in mfg:
                _append_if_exists(product["extended_attributes"], mfg["origin"], "mfg_origin")
            if "made_in" in mfg:
                _append_if_exists(product["extended_attributes"], mfg["made_in"], "mfg_origin")

            brim = value.get("brim", {})
            if "category" in brim:
                _append_if_exists(product["extended_attributes"], brim["category"], "brim_category")
            if "dimension" in brim:
                _append_if_exists(product["extended_attributes"], brim["dimension"], "brim_dimension")

            crown = value.get("crown", {})
            if "type" in crown:
                _append_if_exists(product["extended_attributes"], crown["type"], "crown_type")
            if "dimension" in crown:
                _append_if_exists(product["extended_attributes"], crown["dimension"], "crown_dimension")

    return product


def update_dynamodb_table(dynamodb, product_id, variant_id, netsuite_internal_id, inv_item_id):
    insert_product_variant_data(dynamodb, str(variant_id), str(netsuite_internal_id), str(product_id), str(inv_item_id))


def add_extended_attributes():
    return False


def add_images():
    return False


def _load_json_file(filename):
    with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), filename)) as file:
        return json.load(file)


def _get_non_null_field(array, field, default_value):
    value = array.get(field)
    return default_value if value is None else value


def _remove_tags(text):
    return TAG_RE.sub('', text)


def _append_if_exists(array, value, name):
    if value and array:
        array.append({
            "name": name,
            "value": str(value)
            })


def send_to_queue(product_id, variant_id, inv_item_id):
    message = {
        'product_id': str(product_id),
        'variant_id': str(variant_id),
        'inv_item_id': str(inv_item_id),
    }
    sqs_handler = SqsHandler(queue_name=QUEUE_NAME)
    sqs_handler.push_message(message_group_id=message['variant_id'], message=json.dumps(message))
    LOGGER.info(f'Message pushed to SQS: {sqs_handler.queue_name}')
