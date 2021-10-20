import os
import json
import logging
import asyncio
from easypost_customization.aws.utils import get_newstore_conn

LOGGER = logging.getLogger(__name__)
LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO').upper() or 'INFO'
LOG_LEVEL = getattr(logging, LOG_LEVEL_SET, None)
if not isinstance(LOG_LEVEL, int):
    LOG_LEVEL = getattr(logging, 'INFO', None)
LOGGER.setLevel(LOG_LEVEL)


def handler(event, context):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_process(event, context=context))
    loop.stop()
    loop.close()
    return result


async def _process(event: dict, context=None) -> dict:
    body = event['body']
    LOGGER.info(f'Event payload: {body}')

    body = json.loads(body)
    original_req = body.get('request', {})
    easypost_payload = body.get('shipment_payload', {})
    if original_req['shipping_address']['country_code'] == 'CA':
        LOGGER.info(f'The shipping country is CA, not international. Returning same payload.')
        return {'statusCode': 200, 'body': json.dumps({'customized_payload': easypost_payload})}

    # update easypost_payload with customization fields
    await _add_customs_items_info(
        easypost_payload.get('customs_info', {}).get('customs_items', []), context=context)

    if not easypost_payload['to_address'].get('phone', None):
        easypost_payload['to_address']['phone'] = '0000000000'
    if not easypost_payload['to_address'].get('street2', None):
        easypost_payload['to_address']['street2'] = ''

    LOGGER.info(f'Customized payload: {json.dumps(easypost_payload)}')

    return {'statusCode': 200, 'body': json.dumps({'customized_payload': easypost_payload})}


async def _add_customs_items_info(customs_items, context=None):
    catalog = 'storefront-catalog-en'
    locale = 'en-US'

    for item in customs_items:
        product = get_newstore_conn(context).get_product(
            item['code'], catalog, locale)
        if not product:
            raise Exception(f'No product found for {item["code"]}, failing...')
        LOGGER.info(f'Product details for {item["code"]}: {json.dumps(product)}')

        # add country of origin
        item['origin_country'] = product.get('country_of_origin', '')

        # get hs code for item
        item['hs_tariff_number'] = product.get('product_hts_number', '')

        # add description
        item['description'] = product.get('title', '')
