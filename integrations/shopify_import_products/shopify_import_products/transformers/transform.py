import os
import re
import json
import logging

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)

TAG_RE = re.compile(r'<[^>]+>')

MASTER_PRODUCTS = {}
VARIANT_PRODUCTS = {}
PRODUCT_IMAGES = {}
TRANSFORMED_CATEGORIES = [{
    'path': 'All'
}]


def transform_products(jsonl_data, products_per_file, custom_size_mapping, locale=None):
    build_object_cache([json.loads(line) for line in jsonl_data.splitlines()])

    locale_code = 'en-US' if not locale else locale
    catalog = 'en' if not locale else locale.split('-')[0]
    products_slices = []

    for variants in chunk_products(list(VARIANT_PRODUCTS.values()), products_per_file):
        products_slices.append({
            'head': {
                'locale': locale_code,
                'shop': f'storefront-catalog-{catalog}',
                'is_master': True,
                'filterable_attributes': [
                    {
                        'name': 'fit',
                        'path': "$.extended_attributes[?(@.key == 'final_sale')].value"
                    }
                ],
                'searchable_attributes': [
                    {
                        'name': 'product_id',
                        'path': '$.product_id',
                        'weight': 10
                    },
                    {
                        'name': 'ean13',
                        'path': "$.external_identifiers[?(@.type == 'ean13')].value",
                        'weight': 5
                    },
                    {
                        'name': 'title',
                        'path': '$.product_id',
                        'weight': 10
                    },
                    {
                        'name': 'description',
                        'path': '$.product_id',
                        'weight': 9
                    }
                ],
            },
            'items': [transform_variant(variant, custom_size_mapping, locale) for variant in variants]
        })

    transformed_categories = {
        'head': {
            'locale': locale_code,
            'catalog': f'storefront-catalog-{catalog}'
        },
        'items': TRANSFORMED_CATEGORIES
    }

    return products_slices, transformed_categories


def chunk_products(list_object, count):
    for i in range(0, len(list_object), count):
        yield list_object[i:i + count]


def build_object_cache(json_objects):
    if len(MASTER_PRODUCTS) != 0:
        return

    for current_object in json_objects:
        gid = current_object['id']
        object_type = gid.split('/')[-2]

        if object_type == 'Product':
            MASTER_PRODUCTS[gid] = current_object
        elif object_type == 'ProductVariant':
            sku = current_object.get('sku', None)
            if not sku is None and len(sku) > 0 and sku not in ['Gift Card', 'gift_card_sku']:
                VARIANT_PRODUCTS[gid] = current_object
        elif object_type == 'ProductImage':
            parent_id = current_object['__parentId']
            if not parent_id in PRODUCT_IMAGES:
                PRODUCT_IMAGES[parent_id] = []
            PRODUCT_IMAGES[parent_id].append(current_object)


def transform_variant(variant, custom_size_mapping, locale=None):
    master = MASTER_PRODUCTS[variant['__parentId']]
    tags = master.get('tags', []) or []
    variation_size_value = get_option(1, variant, master)
    size_mapping = get_size_mapping(variation_size_value, custom_size_mapping)

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
        'variation_size_value': variation_size_value,
        'tax_class_id': variant.get('taxCode', '') or '',
        'shipping_dimension_unit': 'cm',
        'images': transform_images(master),
        'external_identifiers': transform_external_identifiers(variant),
        'extended_attributes': transform_extended_attributes(variant, master, tags, size_mapping),
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


def get_size_mapping(variation_size_value, custom_size_mapping):
    upcase_size = variation_size_value.upper()

    return custom_size_mapping[upcase_size] \
        if upcase_size in custom_size_mapping else upcase_size


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
                'alt_text': image.get('altText', '') or ''
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


def transform_extended_attributes(variant, master, tags, size_mapping):
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
    final_sale = is_final_sale(tags)

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

    extended_attributes.append({
        'name': 'final_sale',
        'value': 'true' if final_sale else 'false'
    })

    extended_attributes.append({
        'name': 'size_custom',
        'value': size_mapping
    })

    return extended_attributes


def is_final_sale(tags):
    final_sale = next(filter(lambda tag: 'custitem_fao_finalsale' in tag.lower(), tags), None)

    if final_sale is not None:
        return final_sale.split(':')[1].strip().lower() == 'yes'

    return False


def variant_categories(tags):
    categories = [{
        'path': 'All'
    }]

    categories += build_categories(tags)
    return categories


def build_categories(tags):
    def add_global_category(path):
        global TRANSFORMED_CATEGORIES # pylint: disable=W0603
        if not next(filter(lambda c: c['path'] == path, TRANSFORMED_CATEGORIES), None):
            TRANSFORMED_CATEGORIES.append({
                'path': path
            })

    product_categories = []

    category_tags = [tag.split(':') for tag in tags]
    division_tag = next(filter(lambda ctag: ctag[0] == 'division', category_tags), None)
    merch_department_tag = next(filter(lambda ctag: ctag[0] == 'custitem_fao_merch_department', category_tags), None)

    if division_tag is not None and len(division_tag) >= 2:
        division_tag_value = division_tag[1]
        path = f'All > {division_tag_value}'
        add_global_category(path)
        product_categories.append({
            'path': path
        })

        if merch_department_tag is not None and len(merch_department_tag) >= 2:
            merch_department_tag_value = merch_department_tag[1]
            path = f'All > {division_tag[1]} > {merch_department_tag_value}'
            add_global_category(path)
            product_categories.append({
                'path': path,
                'is_main': True
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
