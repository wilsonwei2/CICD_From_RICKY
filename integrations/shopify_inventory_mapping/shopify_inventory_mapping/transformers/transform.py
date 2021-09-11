import json
import logging

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.INFO)

VARIANT_PRODUCTS = {}


def process_transformation(jsonl_data):
    build_object_cache([json.loads(line) for line in jsonl_data.splitlines()])

    products_slices = []

    for variants in chunk_products(list(VARIANT_PRODUCTS.values()), 1000):
        products_slices.append({
            'items': [transform_variant(variant) for variant in variants]
        })

    LOGGER.info(f'Processed {len(products_slices)} product slices...')

    return products_slices


def chunk_products(list_object, count):
    for i in range(0, len(list_object), count):
        yield list_object[i:i + count]


def build_object_cache(json_objects):
    for current_object in json_objects:
        gid = current_object['id']
        object_type = gid.split('/')[-2]

        if object_type == 'ProductVariant':
            sku = current_object.get('sku', None)
            if not sku is None and len(sku) > 0 and sku not in ['Gift Card', 'gift_card_sku']:
                VARIANT_PRODUCTS[gid] = current_object


def transform_variant(variant):
    variant_id = variant.get('id')
    shopify_product_id = ''
    if variant_id:
        shopify_product_id = str(variant_id.split('/')[-1])

    inventory_item = variant.get('inventoryItem')
    shopify_inventory_item_id = ''
    if inventory_item and 'id' in inventory_item:
        shopify_inventory_item_id = inventory_item['id'].split('/')[-1]

    transformed_variant = {
        'product_sku': variant.get('sku', '') or '',
        'shopify_product_id': shopify_product_id,
        'shopify_inventory_item_id': shopify_inventory_item_id
    }

    return transformed_variant
