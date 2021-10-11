import json
import logging
import os
import copy
from decimal import Decimal
from shopify_import_order.handlers import shopify_helper

PROCESSOR = os.environ.get('PAYMENT_PROCESSOR', 'shopify')
GIFTCARD_ELECTRONIC = os.environ.get('giftcard_electronic', 'EGC')
GIFTCARD_PHYSICAL = os.environ.get('giftcard_physical', 'PGC')
LOGGER = logging.getLogger(__name__)
LOG_LEVEL_SET = os.environ.get('LOG_LEVEL', 'INFO') or 'INFO'
LOG_LEVEL = logging.DEBUG if LOG_LEVEL_SET.lower() in ['debug'] else logging.INFO
LOGGER.setLevel(LOG_LEVEL)
SHOPIFY_CHANNEL = 'MTLDC1'
CITY_SUBSTRING_LIMIT = 49


def transform(transaction_data, order, is_exchange, shop, shipping_offer_token=None):
    order_customer = order.get('customer', {})
    order_name = str(order['name']).replace('#', '')

    LOGGER.info(f"Order external_id: {order_name}")
    LOGGER.info(f"Notes from shopify - {order['note']}")
    LOGGER.debug(order)

    if order.get('shipping_lines', []):
        ship_code = _get_non_null_field(order['shipping_lines'][0], 'code', '').lower()
    else:
        ship_code = ''

    if ship_code in ("pickup in store", "store-pickup"):
        notification_blacklist = ['shipment_dispatched', 'refund_note_created']
    else:
        notification_blacklist = ['shipment_dispatched', 'order_cancelled', 'refund_note_created']

    ns_order = {
        'shop': 'storefront-catalog-en',
        'shop_locale': 'en-US',
        'external_id': f'{order_name}',
        'channel_type': 'web',
        'channel_name': SHOPIFY_CHANNEL,
        'currency': _get_non_null_field(order, 'currency', ''),
        'customer_name': _get_customer_name(order_customer),
        'customer_email': order['email'],
        'customer_locale': _get_non_null_field(order, 'customer_locale', '').upper(),
        'external_customer_id': str(order_customer['id']),
        'placed_at': order['processed_at'],
        'price_method': _get_price_method(order),
        'shipping_address': get_address(order.get('shipping_address', {})),
        'billing_address': get_address(order.get('billing_address', {})),
        'shipments': [
            {
                'items': [],
                'shipping_option': _get_shipping_option(order, shipping_offer_token)
            }
        ],
        'payments': map_payments(transaction_data, order_name, order, is_exchange),
        'extended_attributes': map_extended_attributes(order, order_name, is_exchange, shop),
        'notification_blacklist': notification_blacklist
    }

    if order.get('browser_ip') and order.get('browser_ip') != "None":
        ns_order['ip_address'] = order['browser_ip']

    map_items(order, order_name, ns_order)

    if 'shipping_offer_token' in ns_order['shipments'][0]['shipping_option']:
        del ns_order['shipping_address']
    elif not has_shipment(order) and not order.get('shipping_address', None):
        ns_order['shipping_address'] = ns_order['billing_address']

    return ns_order


def has_shipment(order):
    return next((True for item in order['line_items'] if item['requires_shipping']), False)


def get_address(order_address):
    return {
        'first_name': _get_non_null_field(order_address, 'first_name', ''),
        'last_name': _get_non_null_field(order_address, 'last_name', ''),
        'country': _get_non_null_field(order_address, 'country_code', ''),
        'zip_code': _get_non_null_field(order_address, 'zip', ''),
        'city': _get_non_null_field(order_address, 'city', '')[0:CITY_SUBSTRING_LIMIT],
        'state': _get_non_null_field(order_address, 'province_code', ''),
        'address_line_1': _get_non_null_field(order_address, 'address1', ''),
        'address_line_2': _get_non_null_field(order_address, 'address2', ''),
        'phone': _get_non_null_field(order_address, 'phone', '')
    }


def map_extended_attributes(order, order_name, is_exchange, shop):
    return [
        {
            'name': 'returnly_exchange',
            'value': str(is_exchange)
        },
        {
            'name': 'external_order_id',
            'value': order_name
        }
        ,
        {
            'name': 'external_shop',
            'value': shop
        },
        {
            'name': 'order_id',
            'value': str(order['id'])
        },
        {
            'name': 'ext_channel_name',
            'value': SHOPIFY_CHANNEL
        },
        {
            'name': 'is_historical',
            'value': 'False'
        },
        {
            'name': 'order_memo',
            'value': order['note'] if order['note'] else ''
        }
    ]

def map_exchange_payments(order_name, order):
    payments_list = []
    order_total_price = order.get("total_price")
    if float(order_total_price) > 0.0:
        payments_list.append(
            {
                'processor': "loop",
                'correlation_ref': "correlation_ref",
                'type': 'authorized',
                'amount': float(order_total_price),
                'method': "loop",
                'processed_at': order['processed_at'],
                'metadata': {
                    'external_order_id': order_name,
                    'transaction_id': "Loop default exchange transaction"
                }
            }
        )
    return payments_list


def map_payments(transaction_data, order_name, order, is_exchange):
    #  Map payments information from transaction data
    payments_list = []
    refunded_list = refunded_transactions(transaction_data)
    if is_exchange:
        return map_exchange_payments(order_name=order_name, order=order)
    for transaction in transaction_data:
        if transaction.get('kind') in ('sale', 'authorization') \
                and transaction.get('status') == 'success' \
                and transaction.get('id') not in refunded_list:

            payments_list.append(
                {
                    'processor': PROCESSOR,
                    'correlation_ref': str(transaction['id']),
                    'type': 'authorized',
                    'amount': float(transaction['amount']),
                    'method': _get_payment_method(transaction),
                    'processed_at': transaction['created_at'],
                    'metadata': _get_payment_metadata(transaction=transaction, order_name=order_name, order=order,
                                                      is_exchange=False)
                }
            )
    return payments_list


def map_items(order, order_name, ns_order):
    has_electronic_giftcard = False
    has_shipping_items = False
    final_sale = _is_final_sale(order)
    items = []
    for item in order['line_items']:
        ## Adding Discounts
        discounts = map_discounts(item, order, order_name)
        LOGGER.debug(f'Discounts: \n{json.dumps(discounts, indent=4)}')

        variant_id = item['variant_id']
        p_id = variant_id
        sku = item['sku'].lower().startswith('5500000')

        is_gift_card = item['gift_card'] or sku
        if is_gift_card and item['requires_shipping']:
            # If it's gift card decide the product ID with wheter it requires shipping or not
            has_shipping_items = True
            p_id = GIFTCARD_PHYSICAL
        elif is_gift_card:
            has_electronic_giftcard = True
            p_id = GIFTCARD_ELECTRONIC
        else:
            has_shipping_items = True
            ## Fetching NS ID.
            LOGGER.info(f"Product ID: {item['product_id']} and Variant ID: {variant_id}")
            p_id = item['sku']
            LOGGER.info(f'{p_id} is the product id')

        for qty in range(item['quantity']):
            item_price = item['price']
            item_tax_lines, tax_lines_highs_lows = map_taxes(item)

            ns_item = {
                'external_item_id': str(variant_id),
                'product_id':str(p_id),
                'item_tax_lines':item_tax_lines,
                'price':{
                    'item_price':float(item_price),
                    'item_list_price': float(item_price),
                    'item_tax_lines': None,
                    **discounts['price']
                },
                # external_item_id is being added in extended_attributes as well because
                # it doesn't show on customer_order or external_order payloads.
                'extended_attributes': [
                    {
                        'name': 'is_gift_card',
                        'value': str(is_gift_card)
                    },
                    {
                        'name': 'requires_shipping',
                        'value': str(item['requires_shipping'])
                    },
                    {
                        'name': 'external_item_id',
                        'value': str(item['id'])
                    },
                    {
                        'name': 'final_sale',
                        'value': 'true' if final_sale else 'false'
                    }
                ]
            }

            for index, tax_line in enumerate(item_tax_lines):
                tax_line['amount'] = float(tax_lines_highs_lows[index][0] / 100) \
                    if qty + 1 <= tax_lines_highs_lows[index][2] \
                    else float(tax_lines_highs_lows[index][1] / 100)

            ns_item['price']['item_tax_lines'] = item_tax_lines
            new_item = copy.deepcopy(ns_item)
            #  Adjust discounts
            # Item level discount
            _adjust_discount_price(
                new_item['price']['item_discount_info'], item['quantity'], qty)
            # Order level discount
            _adjust_discount_price(
                new_item['price']['item_order_discount_info'], item['quantity'], qty)
            items.append(new_item)

    ## Adding shipping lines at the end based on the electronic giftcard type.
    if not has_shipping_items and has_electronic_giftcard:
        ns_order['shipping_address'] = ns_order['billing_address']

    ns_order['shipments'][0]['items'] = items


def map_discounts(item, order, order_name):
    discounts = {
        'price': {
            'item_discount_info': [],
            'item_order_discount_info': []
        }
    }
    for discount_allocation in item.get('discount_allocations', []):
        discount = order['discount_applications'][discount_allocation['discount_application_index']]

        discount_item = _get_discount_item(discount, discount_allocation, order_name)
        # Item level discount
        if discount['target_selection'] in ['entitled', 'explicit']:
            if not discounts['price']['item_discount_info']:
                discounts['price']['item_discount_info'].append(discount_item)
            else:
                _add_discount(discounts['price']['item_discount_info'][0], discount_item)
        # Order level discount
        else:
            if not discounts['price']['item_order_discount_info']:
                discounts['price']['item_order_discount_info'].append(discount_item)
            else:
                _add_discount(discounts['price']['item_order_discount_info'][0], discount_item)
    return discounts


def map_taxes(item):
    item_tax_lines = []
    tax_lines_highs_lows = []
    for tax_lines in item['tax_lines']:
        tax_lines_highs_lows.append(_even_split(
            Decimal(tax_lines['price']), item['quantity']))
        item_tax_lines.append(
            {
                'amount': 0.0,
                'rate': float(tax_lines['rate']),
                'name': _get_non_null_field(tax_lines, 'title', '')
            }
        )
    return item_tax_lines, tax_lines_highs_lows


def _is_final_sale(order):
    return 'final sale' in order.get('tags', '').lower()


def _add_discount(discount_master, added_discount):
    '''
    When there's more then one discount per order level or per item level they
    add up since NewStore expects only one discount per order level or item level
    in each product. Since the discounts can be a mix of percentage with percentage
    or percentage with fixed when the add occurs the discount turns into fixed
    '''
    discount_master['type'] = 'fixed'
    discount_master['price_adjustment'] += added_discount['price_adjustment']
    discount_master['discount_ref'] = ';'.join(
        filter(None, [discount_master['discount_ref'], added_discount['discount_ref']]))
    discount_master['original_value'] = discount_master['price_adjustment']


def _get_discount_item(discount, discount_allocation, order_name):
    discount_type = 'percentage' if discount['value_type'] == 'percentage' else 'fixed'
    price_adjustment = discount_allocation['amount']
    original_value = discount['value'] if discount_type == 'percentage' else price_adjustment
    discount_ref = _get_discount_ref(discount, order_name)
    return {
        'type': discount_type,
        'original_value': float(original_value),
        'price_adjustment': float(price_adjustment),
        'discount_ref': discount_ref,
        'coupon_code': _get_non_null_field(discount, 'code', ''),
        'description': _get_non_null_field(discount, 'description', '')
    }


def _get_discount_ref(discount_app, order_name):
    '''
    Item level Discount
    '''
    dicount_ref = discount_app.get('code', discount_app.get(
        'title', discount_app.get('description')))
    if dicount_ref:
        return dicount_ref
    return order_name


def _adjust_discount_price(discount_info, quantity, index):
    for discount in discount_info:
        price_adjustments = _even_split(
            Decimal(discount['price_adjustment']), quantity)
        price_adjustment = price_adjustments[0] if index + \
                                                   1 <= price_adjustments[2] else price_adjustments[1]
        discount['price_adjustment'] = float(Decimal(price_adjustment)/100)


## Used in item pricing
def _even_split(dollars, qty):
    low, highs = divmod(dollars * 100, qty)
    high = low + 1
    lows = qty - highs
    return (low, high, int(round(lows)), int(round(highs)))


def _get_payment_metadata(transaction, order_name, order, is_exchange):
    # Mapping all the requirement for the Newstore Metadata
    if not is_exchange:
        payment_metadata = {
            'external_order_id': order_name,
            'shopify_order_id': str(order['id']),
            'channel': SHOPIFY_CHANNEL,
            'transaction_id': str(transaction['id'])
        }
    else:
        payment_metadata = {
            'external_order_id': order_name,
            'channel': SHOPIFY_CHANNEL,
            'transaction_id': str(transaction['id'])
        }


    shopify_payment_details = transaction.get('payment_details', {})

    for key in shopify_payment_details:
        payment_metadata[key] = _get_non_null_field(shopify_payment_details, key, '')

    payment_method = _get_payment_method(transaction)

    if payment_method == 'gift_card' and not is_exchange:
        ## Need to add the gift card validation here. -- Should not be a return.
        payment_metadata['number'] = transaction['receipt']['gift_card_last_characters']

    return payment_metadata


def _get_payment_method(order):
    if order['gateway'] == 'shopify_payments':
        return 'credit_card'

    if order['gateway'] == 'Cash on Delivery (COD)':
        return 'cash'

    return order['gateway']


def _get_non_null_field(order, field, default_value):
    value = order.get(field)
    return default_value if value is None else value


def _get_customer_name(order_customer):
    '''
    Adding customer name to the order
    '''
    first_name = order_customer['first_name']
    last_name = order_customer['last_name']
    return f'{first_name} {last_name}'


def _get_price_method(order):
    return 'tax_included' if order['taxes_included'] else 'tax_excluded'


def refunded_transactions(transaction_data):
    '''
    Refunded Transaction data
    '''
    refunded = []
    for transaction in transaction_data:
        if transaction.get('kind') == 'refund' and transaction.get('status') == 'success':
            refunded.append(transaction['parent_id'])
    return refunded


def _get_shipping_option(order, shipping_offer_token):
    '''
    Get shipping option -- original and should work,
    the call is made in transform.
    '''
    shipping_lines = order.get('shipping_lines', [])
    LOGGER.info('Inside shipping options')

    shipping_address = order.get('shipping_address', {})
    shipping_country_code = ''

    if 'country_code' in shipping_address:
        shipping_country_code = shipping_address['country_code']

    if shipping_lines:
        if shipping_offer_token is not None:
            shipping_option = {
                'shipping_offer_token': shipping_offer_token,
                'price': 0.0,
                'tax': 0.0
            }
        else:
            code = _get_non_null_field(shipping_lines[0], 'code', '').lower()
            title = _get_non_null_field(shipping_lines[0], 'title', '').lower()
            service_level_identifier = shopify_helper.get_shipment_service_level(code, title, shipping_country_code)
            LOGGER.info(f'Service level identified from is {service_level_identifier}')
            shipping_option = {
                'service_level_identifier': service_level_identifier,
                'price': float(shipping_lines[0]['price']),
                'tax': _get_shipping_taxes(shipping_lines[0])
            }

            if len(_get_non_null_field(shipping_lines[0], 'discount_allocations', [])) > 0:
                shipping_discount = shipping_lines[0]['discount_allocations'][0]
                shipping_discount_info = {
                    'discount_ref': 'Shipping Discount',
                    'type': 'fixed',
                    'original_value': float(shipping_lines[0]['price']),
                    'price_adjustment': float(shipping_discount['amount']),
                }

                _add_shipping_discount_code(order, shipping_discount_info)

                shipping_option['discount_info'] = [shipping_discount_info]

    else:
        service_level_identifier = shopify_helper.get_shipment_service_level('default', 'default', shipping_country_code) # Get default
        LOGGER.warning(f"Order doesn't have shipping lines, utilizing default shipping {service_level_identifier}.")

        shipping_option = {
            'service_level_identifier': service_level_identifier,
            'price': 0.0,
            'tax': 0.0
        }

    LOGGER.debug(f'Returned shipping option is {shipping_option}')
    return shipping_option


def _get_shipping_taxes(shipping_line):
    shipping_taxes_total = 0.0
    for tax in shipping_line['tax_lines']:
        shipping_taxes_total += float(tax.get('price', '0.0'))
    return round(shipping_taxes_total, 2)


def _add_shipping_discount_code(order, shipping_discount_info):
    if len(_get_non_null_field(order, 'discount_codes', [])) > 0:
        for discount_code in order['discount_codes']:
            if _get_non_null_field(discount_code, 'type', '') == 'shipping':
                shipping_discount_info['coupon_code'] = discount_code['code']
