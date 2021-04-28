# -*- coding: utf-8 -*-
# Copyright (C) 2015, 2016, 2017 NewStore, Inc. All rights reserved.
import os
import json
import asyncio
from collections.abc import Mapping

# Runs startup processes
import netsuite.netsuite_environment_loader # pylint: disable=W0611
import netsuite.api.sale as ns_s
import netsuite.api.refund as ns_r
import netsuite.api.customer as ns_c
from netsuite.service import RecordRef
from zeep.helpers import serialize_object

import netsuite_appeasement_refund_injection.transformers.process_appeasement as pa
import netsuite_appeasement_refund_injection.helpers.sqs_consumer as sqs_consumer
from netsuite_appeasement_refund_injection.helpers.utils import Utils
from netsuite_appeasement_refund_injection.helpers.utils import LOGGER

SQS_QUEUE = os.environ['SQS_QUEUE']


def handler(_event, context):
    LOGGER.info(f'Beginning queue retrieval...')
    # Initialize newstore conector
    Utils.get_newstore_conn(context)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = sqs_consumer.consume(process_appeasement, SQS_QUEUE)
    loop.run_until_complete(task)
    loop.stop()
    loop.close()


async def process_appeasement(message):
    LOGGER.info(f"Message to process: \n {json.dumps(message, indent=4)}")
    event_refund = message['payload']
    order_id = event_refund['order_id']
    customer_order = await get_customer_order(order_id)
    payments_info = Utils.get_newstore_conn().get_payments(order_id)
    store_tz = await get_store_tz_by_customer_order(customer_order)
    LOGGER.info(f'Timezone: {store_tz}')

    is_endless_aisle = Utils.is_endless_aisle(order_payload=customer_order)
    # In case of Endless Aisle channel_type is store, but it needs to be treated as web
    if is_endless_aisle:
        LOGGER.info('Endless Aisle order, proceed to create a standalone CashRefund')
        return await handle_online_order(event_refund, payments_info, customer_order, store_tz)

    if customer_order['channel_type'] == 'store':
        LOGGER.info('In store order, proceed to create a CashRefund from a CashSale')
        return await handle_in_store_order(event_refund, payments_info, customer_order, store_tz)
    LOGGER.info("Order is neither Cash and Carry nor Endless Aisle, "
                f"thus will be ignored. Channel type: {customer_order['channel_type']}")


async def handle_online_order(event_refund, payments_info, customer_order, store_tz):
    Utils.replace_associate_id_for_email(customer_order=customer_order)
    consumer = await get_consumer_info(customer_order.get('consumer', {}).get('email'))
    cash_refund = await pa.transform_online_order_refund(consumer, event_refund, customer_order, payments_info, store_tz)
    LOGGER.info(f"Transformed refund data: \n {json.dumps(serialize_object(cash_refund), indent=4, default=Utils.json_serial)}")
    return await handle_generic_return(cash_refund=cash_refund)


async def handle_in_store_order(event_refund, payments_info, customer_order, store_tz):
    cash_sale = await get_cash_sale(customer_order['sales_order_external_id'])
    cash_refund = await pa.transform_in_store_order_refund(cash_sale, event_refund, customer_order, payments_info, store_tz)
    LOGGER.info(f"Transformed refund data: \n {json.dumps(serialize_object(cash_refund), indent=4, default=Utils.json_serial)}")
    return await handle_generic_return(cash_refund=cash_refund)


async def handle_generic_return(cash_refund):
    customer = await get_or_create_customer(cash_refund)
    cash_refund['entity'] = RecordRef(internalId=customer['internalId'])
    result, refund = ns_r.create_cash_refund(cash_refund)
    if result:
        LOGGER.info('CashRefund created successfully.')
    else:
        LOGGER.error('Error on creating CashRefund. CashRefund not created.')
        for status in refund.status.statusDetail:
            if status.code == 'DUP_RCRD':
                LOGGER.info('This record already exists in NetSuite and will be removed from queue.')
                return True
    return result


async def get_or_create_customer(cash_refund):
    customer = cash_refund['entity']

    if isinstance(customer, Mapping):
        internal_id = ns_c.lookup_customer_id_by_name_and_email(customer)
    else:
        internal_id = customer['internalId']

    if internal_id:
        LOGGER.info('Customer exists, we will update it')
        customer['internalId'] = internal_id
        return ns_c.update_customer(customer)

    LOGGER.info('Create new Customer.')
    # This returns the Customer or None if there is any error
    return ns_c.create_customer(customer)


async def get_consumer_info(email):
    if not email:
        return None
    LOGGER.info('Getting consumer info from NewStore.')
    consumer = Utils.get_newstore_conn().get_consumer(email)
    assert consumer, "Couldn't get consumer profile from  NewStore"
    return consumer


async def get_customer_order(order_id):
    LOGGER.info('Getting customer order from NewStore.')
    customer_order = Utils.get_newstore_conn().get_customer_order(order_id)
    assert customer_order, "Couldn't get customer_order from Newstore."
    LOGGER.info(f"Customer order from NewStore\n {json.dumps(customer_order.get('customer_order', {}))}")
    return customer_order.get('customer_order', {})


async def get_cash_sale(order_id):
    LOGGER.info('Getting CashSale from NetSuite.')
    cash_sale = ns_s.get_cash_sale(order_id)
    assert cash_sale, "Couldn't get CashSale from NetSuite."
    return cash_sale


async def get_store_tz_by_customer_order(customer_order):
    if customer_order['placement_location']['id']:
        store_id = customer_order['placement_location']['id']
        store = Utils.get_newstore_conn().get_store(store_id)
        return store.get('timezone')

    if customer_order.get('products', [{}])[0].get('fulfillment_location', None):
        fulfillment_location = customer_order['products'][0]['fulfillment_location']
        if fulfillment_location in Utils.get_dc_timezone_mapping_config():
            return Utils.get_dc_timezone_mapping_config()[fulfillment_location]

    return Utils.get_dc_timezone_mapping_config()['DEFAULT']
