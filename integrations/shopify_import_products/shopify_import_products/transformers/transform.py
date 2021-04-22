import os
import json
import logging
from shopify_import_products.transformers.constants import TAG_RE, CATEGORIES

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)

MASTER_PRODUCTS = {}
VARIANT_PRODUCTS = {}
PRODUCT_IMAGES = {}
TRANSFORMED_CATEGORIES = [{
    'path': 'All'
}]


def transform_products(jsonl_data, locale=None):
    build_object_cache([json.loads(line) for line in jsonl_data.splitlines()])

    locale_code = 'en-US' if not locale else locale
    catalog = 'en' if not locale else locale.split('-')[0]

    transformed_products = {
        'head': {
            'locale': locale_code,
            'shop': f'storefront-catalog-{catalog}',
            'is_master': not locale,
            'internal_disable_image_processing': True
        },
        'items': [transform_variant(variant, locale) for variant in VARIANT_PRODUCTS.values()]
    }

    transformed_categories = {
        'head': {
            'locale': locale_code,
            'catalog': f'storefront-catalog-{catalog}',
            'internal_disable_image_processing': True
        },
        'items': TRANSFORMED_CATEGORIES
    }

    return transformed_products, transformed_categories


def build_object_cache(json_objects):
    if len(MASTER_PRODUCTS) != 0:
        return

    for current_object in json_objects:
        gid = current_object['id']
        object_type = gid.split('/')[-2]

        if object_type == 'Product':
            MASTER_PRODUCTS[gid] = current_object
        elif object_type == 'ProductVariant':
            sku = current_object.get('sku', '')
            if sku != '' and sku not in ['Gift Card', 'gift_card_sku']:
                VARIANT_PRODUCTS[gid] = current_object
        elif object_type == 'ProductImage':
            parent_id = current_object['__parentId']
            if not parent_id in PRODUCT_IMAGES:
                PRODUCT_IMAGES[parent_id] = []
            PRODUCT_IMAGES[parent_id].append(current_object)


def transform_variant(variant, locale=None):
    master = MASTER_PRODUCTS[variant['__parentId']]
    tags = master.get('tags', []) or []

    transformed_variant = {
        'is_searchable': True,
        'is_published': True,
        'show_in_listing': True,
        'product_id': variant.get('sku', '') or '',
        'variant_group_id': master['id'].split('/')[-1],
        'brand': master.get('vendor', '') or '',
        'title': master.get('title', '') or '',
        'caption': master.get('title', '') or '',
        'description': remove_tags(master.get('bodyHtml', '') or ''),
        'keywords': tags,
        'shipping_weight_unit': transform_weight_unit(variant.get('weightUnit', None)),
        'shipping_weight_value': float(variant.get('weight', 2)) or 2,
        'variation_color_value': get_option(2, variant, master),
        'variation_size_value': get_option(1, variant, master),
        'tax_class_id': variant.get('taxCode', '') or '',
        'shipping_dimension_unit': 'cm',
        'images': transform_images(master),
        'external_identifiers': transform_external_identifiers(variant),
        'extended_attributes': transform_extended_attributes(variant, master),
        'shipping_dimension_length': 0.0,
        'shipping_dimension_width': 0.0,
        'shipping_dimension_height': 0.0,
        'material': '',
        'google_category': 'none',
        'categories': variant_categories(tags),
        'manufacturer': ''
    }

    if locale:
        transformed_variant = translate_attributes(transformed_variant, master.get('translations'))

    return transformed_variant


def get_option(position, variant, master):
    master_option = next(filter(lambda o: o['position'] == position, master['options']), None)

    if not master_option:
        return ''

    variant_option = next(filter(lambda o: o['name'] == master_option['name'], variant['selectedOptions']), None)

    if not variant_option:
        return ''

    return variant_option.get('value', '') or ''


def transform_weight_unit(unit):
    if unit == 'KILOGRAMS':
        return 'kg'

    return 'lb'


def transform_images(master):
    url_image_placeholder = os.environ['url_image_placeholder']

    images = [{
        'url': url_image_placeholder,
        'is_main': True
    }]

    for i, image in enumerate(PRODUCT_IMAGES.get(master['id'], [])):
        if i == 0:
            images = [{
                'url': image.get('originalSrc', url_image_placeholder) or url_image_placeholder,
                'alt_text': image.get('altText', '') or '',
                'is_main': True
            }]
        else:
            images.append({
                'url': image.get('originalSrc', url_image_placeholder) or url_image_placeholder,
                'alt_text': image.get('altText', '') or '',
                'is_color_swatch': False
            })

    return images


def transform_external_identifiers(variant):
    external_identifiers = []

    sku = variant.get('sku')
    inventory_item = variant.get('inventoryItem')
    barcode = variant.get('barcode')

    if sku:
        external_identifiers.append({
            'type': 'sku',
            'value': sku
        })

    if inventory_item and 'id' in inventory_item:
        external_identifiers.append({
            'type': 'shopify_inventory_item_id',
            'value': inventory_item['id'].split('/')[-1]
        })

    if barcode:
        external_identifiers.append({
            'type': 'upc',
            'value': barcode
        })
        external_identifiers.append({
            'type': 'isbn',
            'value': barcode
        })
        external_identifiers.append({
            'type': 'ean13',
            'value': barcode
        })

    return external_identifiers


def transform_extended_attributes(variant, master):
    extended_attributes = []

    master_created_at = master.get('createdAt')
    master_updated_at = master.get('updatedAt')
    master_published_at = master.get('publishedAt')
    master_handle = master.get('handle')
    variant_id = variant.get('id')
    variant_created_at = variant.get('createdAt')
    variant_updated_at = variant.get('updatedAt')
    variant_inventory_management = variant.get('inventoryManagement')
    variant_inventory_policy = variant.get('inventoryPolicy')
    variant_fulfillment_service = maybe(lambda d: d.get('handle'))(variant.get('fulfillmentService'))
    variant_inventory_item = maybe(lambda d: d.get('id'))(variant.get('inventoryItem'))

    if master_created_at:
        extended_attributes.append({
            'name': 'product_created_at',
            'value': str(master_created_at)
        })

    if master_updated_at:
        extended_attributes.append({
            'name': 'product_updated_at',
            'value': str(master_updated_at)
        })

    if master_published_at:
        extended_attributes.append({
            'name': 'product_published_at',
            'value': str(master_published_at)
        })

    if master_handle:
        extended_attributes.append({
            'name': 'product_handle',
            'value': str(master_handle)
        })

    if variant_id:
        extended_attributes.append({
            'name': 'shopify_variant_id',
            'value': str(variant_id.split('/')[-1])
        })

    if variant_created_at:
        extended_attributes.append({
            'name': 'variant_created_at',
            'value': str(variant_created_at)
        })

    if variant_updated_at:
        extended_attributes.append({
            'name': 'variant_updated_at',
            'value': str(variant_updated_at)
        })

    if variant_inventory_management:
        extended_attributes.append({
            'name': 'inventory_management',
            'value': str(variant_inventory_management)
        })

    if variant_inventory_policy:
        extended_attributes.append({
            'name': 'inventory_policy',
            'value': str(variant_inventory_policy)
        })

    if variant_fulfillment_service:
        extended_attributes.append({
            'name': 'fulfillment_service',
            'value': str(variant_fulfillment_service)
        })

    if variant_inventory_item:
        extended_attributes.append({
            'name': 'inventory_item_id',
            'value': str(variant_inventory_item.split('/')[-1])
        })

    return extended_attributes


def variant_categories(tags):
    categories = [{
        'path': 'All'
    }]

    for main_category in CATEGORIES:
        if main_category in tags:
            categories += build_categories(main_category, tags)

    return categories


def build_categories(main_category, tags):
    def defined_in(categories, path):
        return next(filter(lambda c: c['path'] == path, categories), None)

    product_categories = []
    path = f'All > {main_category.capitalize()}'
    product_categories.append({
        'path': path,
        'is_main': True
    })

    global TRANSFORMED_CATEGORIES # pylint: disable=W0603
    if not defined_in(TRANSFORMED_CATEGORIES, path):
        TRANSFORMED_CATEGORIES.append({
            'path': path,
            'is_main': True
        })

    for sub_category in CATEGORIES[main_category]:
        if sub_category in tags:
            sub_path = f'{path} > {CATEGORIES[main_category][sub_category]}'

            product_categories.append({
                'path': sub_path
            })

            if not defined_in(TRANSFORMED_CATEGORIES, sub_path):
                TRANSFORMED_CATEGORIES.append({
                    'path': sub_path,
                    'is_main': False
                })

    return product_categories


def translate_attributes(transformed_variant, translations):
    title_translation = next(filter(lambda t: t['key'] == 'title', translations), None)
    body_html_translation = next(filter(lambda t: t['key'] == 'body_html', translations), None)

    if title_translation:
        transformed_variant['title'] = title_translation.get('value', '') or ''
        transformed_variant['caption'] = title_translation.get('value', '') or ''

    if body_html_translation:
        transformed_variant['description'] = remove_tags(body_html_translation.get('value', '') or '')

    return transformed_variant


def remove_tags(text):
    return TAG_RE.sub('', text)


def maybe(func):
    def wrapper(arg):
        return None if arg is None else func(arg)
    return wrapper
