import logging
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TRUE_VALUES = ['1', 'yes', 'true', 1]


###
# Receive and verify the payments payload of an NewStore order
# Update the payment info if necessary
###
def verify_and_update_missing_payment_info(shopify_conn, payments_info, customer_order):
    logger.info('Verify and update missing payment info for credit card payments.')
    if is_shopify_order(customer_order):
        logger.info('Order is Shopify order, check if it has the necessary payment info.')
        shopify_transactions = None
        
        for instrument in payments_info['instruments']:
            for original_transaction in instrument['original_transactions']:
                payment_method = original_transaction['payment_method']
                if payment_method == 'credit_card':
                    if 'credit_card_company' in original_transaction['metadata']:
                        logger.info('Order has the necessary information.')
                        return payments_info
                    else:
                        if not shopify_transactions:
                            logger.info('Order is missing credit card company information, fetch from Shopify.')
                            shopify_order_id = get_extended_attribute(customer_order['extended_attributes'], 'order_id')
                            logger.info('Get transactions from Shopify order id %s.' % (shopify_order_id))
                            shopify_transactions = get_shopify_credit_card_transactions(
                                                                        shopify_conn, 
                                                                        shopify_order_id
                                                                        )
                            logger.info('Shopify transactions filtered:\n%s' % (json.dumps(shopify_transactions, indent=4)))
                        
                        for transaction in shopify_transactions:
                            if (abs(float(transaction['amount'])) == abs(float(original_transaction['capture_amount']))) or \
                                    (abs(float(transaction['amount'])) == abs(float(original_transaction['refund_amount']))):
                                brand = transaction['payment_details']['credit_card_company']
                                logger.info('Put brand %s on orignal transaction metadata' % brand)
                                original_transaction['metadata']['credit_card_company'] = brand
                                shopify_transactions.remove(transaction)
                                break
        logger.info('Payments info:\n%s' % (json.dumps(payments_info, indent=4)))
    else:
        logger.info('Order is not shopify order, no need to change anything.')
    return payments_info


def is_shopify_order(customer_order):
    return customer_order['channel_type'] == 'web'


def get_shopify_credit_card_transactions(shopify_conn, order_id):
    shopify_transactions = shopify_conn.transaction_data({'id':order_id})
    logger.info('Shopify transactions:\n%s' % (json.dumps(shopify_transactions, indent=4)))
    transactions = []
    transactions_map = {}
    for transaction in shopify_transactions:
        if transaction['status'] == 'success' \
                and transaction['gateway'] == 'shopify_payments':
            if transaction['kind'] == 'sale' or transaction['kind'] == 'authorization':
                transactions_map[transaction['id']] = transaction['payment_details']
            else:
                root_trans_id = get_root_transaction_id(transaction['parent_id'], shopify_transactions)
                transaction['payment_details'] = transactions_map[root_trans_id]
            transactions.append(transaction)
    return transactions


def get_extended_attribute(extended_attributes, key):
    if extended_attributes:
        for attr in extended_attributes:
            if attr['name'] == key:
                return attr['value']
    return ''


def get_root_transaction_id(parent_id, shopify_transactions):
    for transaction in shopify_transactions:
        if transaction['id'] == parent_id:
            if transaction['parent_id']:
                return get_root_transaction_id(transaction['parent_id'], shopify_transactions)
    return parent_id


def retrieve_captured_amount(transaction, currency_id):
    amount = 0
    if transaction['capture_amount'] != 0:
        if currency_id == int(os.environ['currency_cad_internal_id']) and transaction['payment_method'] == 'cash':
            amount = transaction['capture_amount']
            round_value = 0.05
            amount = round_nearest(amount, round_value)
        else:
            amount = transaction['capture_amount']
    logger.info("retrieve_captured_amount - amount %s", amount)
    return amount


def round_nearest(x, a):
    return round(x / a) * a


def is_shopify_historic_order(customer_order):
    is_historical = get_extended_attribute(customer_order.get('extended_attributes', []), 'is_historical')
    return is_historical.lower() in TRUE_VALUES


def get_authorized_transactions(payments_info):
    authorization_transactions = []
    for instrument in payments_info['instruments']:
        for original_transaction in instrument['original_transactions']:
            if original_transaction['reason'] == 'authorization':
                authorization_transactions.append(original_transaction)
    return authorization_transactions


def get_formated_phone(phone):
    regex = r'^\D?(\d{3})\D?\D?(\d{3})\D?(\d{4})$'
    phone = phone if re.match(regex, phone) else '5555555555'
    phone = re.sub(regex, r'\1-\2-\3', phone)
    return phone


def get_phone(consumer):
    phone = consumer.get('phone') if consumer.get('phone') else consumer.get('contact_phone')
    if not phone:
        for address in consumer.get('addresses',[]):
            phone = address.get('contact_phone')
            if phone:
                break
    return phone if phone else '5555555555'


def calcule_tax_rate(price,tax):
    data = tax*100/price
    return round(data,4)


def is_virtual_gift_card(line_item):
    is_gc = get_extended_attribute(line_item['extended_attributes'], 'is_gift_card')
    requires_shipping = get_extended_attribute(line_item['extended_attributes'], 'requires_shipping')
    return is_gc == 'True' and requires_shipping == 'False'


def is_gift_card(line_item):
    is_gc = get_extended_attribute(line_item['extended_attributes'], 'is_gift_card')
    return is_gc.lower() == 'true'
