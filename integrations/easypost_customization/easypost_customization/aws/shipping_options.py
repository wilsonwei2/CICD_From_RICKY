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


async def _process(event: dict, context=None) -> dict:  # pylint: disable=unused-argument
    body = event['body']
    LOGGER.info(f'Event payload: {body}')

    body = json.loads(body)
    original_req = body.get('request', {})
    easypost_payload = body.get('shipment_payload', {})

    if original_req['shipping_address']['country_code'] == 'CA':
        LOGGER.info(f'The shipping country is CA, not international. Returning same payload.')
        return {'statusCode': 200, 'body': json.dumps({'customized_payload': easypost_payload})}

    # Add the customs_items information to the request for Easypost
    customs_items = []
    catalog = 'storefront-catalog-en'
    locale = 'en-US'
    deliverables = original_req.get('deliverables', [])
    for entry in deliverables:
        item = entry['item']
        product = get_newstore_conn(context).get_product(
            item['identifier']['product_id'], catalog, locale)
        if not product:
            raise Exception(f'No product found for {item["identifier"]["product_id"]}, failing...')

        customs_item = {
            'code': item['identifier']['product_id'],
            'description': product.get('title', ''),
            'origin_country': product.get('country_of_origin', ''),
            'hs_tariff_number': product.get('product_hts_number', ''),
            'quantity': 1
        }

        customs_items.append(customs_item)

    easypost_payload['customs_info'] = {
        'customs_signer': 'Frank and Oak',
        'customs_items': customs_items
    }

    LOGGER.info(f'Transformed payload: {json.dumps(easypost_payload)}')

    return {'statusCode': 200, 'body': json.dumps({'customized_payload': easypost_payload})}
