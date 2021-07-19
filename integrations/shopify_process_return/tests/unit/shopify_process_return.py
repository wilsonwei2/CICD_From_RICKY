from pathlib import Path
import logging
import requests_mock


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

#Unifinished test


def test_shopify_process_return():
    event = {
        "Records": [
            {
                "messageId": "2bc3023e-9182-4492-bd49-15dd52f9d545",
                "receiptHandle": "AQEBZiSF/lljo5tExNrcTH1Y4OqCDtajuDVLeBlNwQjCOvaep+E6PCWQhUEBtPw9zvNUFqEHiUunzIiiWoA7TOXLayZzecc5FyT4m0SCtDMZIeNJ9z2+1v7D9Qf5RRhNVF/xEa4RU9I9SkLxLPraxmX5r1j5xpO2GRFo2wykGTwiCxOeNtBVzndwYMswws1V16ujbEF8tmJeFJSoMBMwG3nZGIrUyntMayKyOk5LRkwSw2DI4rozNCBXtLkt9GC1EhgSJgT4JxuCC9equL+zik8cBQ0YiZamBfK51D+HHiA8/5eocXlsviHs6tv++OOvafO0Rq8AoBFlG4Mbeuhbh4NL75rYRRyC1AALO0kM1pVvVIOBeJZW1/j9BspUF2x5K6Z0I7Y78jC/xLFG0Z2wDkuTrCb1ECYDboMnRT2lJxNM10E=",
                "body": "{\"id\": 812249841820, \"order_id\": 4009148350620, \"created_at\": \"2021-07-05T06:25:22-04:00\", \"note\": \"test\", \"user_id\": 73285632156, \"processed_at\": \"2021-07-05T06:25:22-04:00\", \"restock\": false, \"duties\": [], \"total_duties_set\": {\"shop_money\": {\"amount\": \"0.00\", \"currency_code\": \"CAD\"}, \"presentment_money\": {\"amount\": \"0.00\", \"currency_code\": \"CAD\"}}, \"admin_graphql_api_id\": \"gid://shopify/Refund/812249841820\", \"refund_line_items\": [{\"id\": 304883826844, \"quantity\": 1, \"line_item_id\": 10193381687452, \"location_id\": null, \"restock_type\": \"no_restock\", \"subtotal\": 39.97, \"total_tax\": 5.99, \"subtotal_set\": {\"shop_money\": {\"amount\": \"39.97\", \"currency_code\": \"CAD\"}, \"presentment_money\": {\"amount\": \"39.97\", \"currency_code\": \"CAD\"}}, \"total_tax_set\": {\"shop_money\": {\"amount\": \"5.99\", \"currency_code\": \"CAD\"}, \"presentment_money\": {\"amount\": \"5.99\", \"currency_code\": \"CAD\"}}, \"line_item\": {\"id\": 10193381687452, \"variant_id\": null, \"title\": \"\\\"Good\\\" Cotton City Jogger in Black\", \"quantity\": 1, \"sku\": \"1210161-002-34\", \"variant_title\": \"34\", \"vendor\": \"Frank and Oak\", \"fulfillment_service\": \"manual\", \"product_id\": null, \"requires_shipping\": true, \"taxable\": true, \"gift_card\": false, \"name\": \"\\\"Good\\\" Cotton City Jogger in Black - 34\", \"variant_inventory_management\": null, \"properties\": [], \"product_exists\": false, \"fulfillable_quantity\": 0, \"grams\": 700, \"price\": \"39.97\", \"total_discount\": \"0.00\", \"fulfillment_status\": \"fulfilled\", \"pre_tax_price\": \"39.97\", \"price_set\": {\"shop_money\": {\"amount\": \"39.97\", \"currency_code\": \"CAD\"}, \"presentment_money\": {\"amount\": \"39.97\", \"currency_code\": \"CAD\"}}, \"pre_tax_price_set\": {\"shop_money\": {\"amount\": \"39.97\", \"currency_code\": \"CAD\"}, \"presentment_money\": {\"amount\": \"39.97\", \"currency_code\": \"CAD\"}}, \"total_discount_set\": {\"shop_money\": {\"amount\": \"0.00\", \"currency_code\": \"CAD\"}, \"presentment_money\": {\"amount\": \"0.00\", \"currency_code\": \"CAD\"}}, \"discount_allocations\": [], \"duties\": [], \"admin_graphql_api_id\": \"gid://shopify/LineItem/10193381687452\", \"tax_lines\": [{\"title\": \"CANADA GST/TPS\", \"price\": \"2.00\", \"rate\": 0.05, \"price_set\": {\"shop_money\": {\"amount\": \"2.00\", \"currency_code\": \"CAD\"}, \"presentment_money\": {\"amount\": \"2.00\", \"currency_code\": \"CAD\"}}}, {\"title\": \"QUEBEC QST/TVQ\", \"price\": \"3.99\", \"rate\": 0.09975, \"price_set\": {\"shop_money\": {\"amount\": \"3.99\", \"currency_code\": \"CAD\"}, \"presentment_money\": {\"amount\": \"3.99\", \"currency_code\": \"CAD\"}}}], \"origin_location\": {\"id\": 2909206184092, \"country_code\": \"CA\", \"province_code\": \"QC\", \"name\": \"Frank And Oak Store Dev CAN\", \"address1\": \"110-160, rue Saint-Viateur Est\", \"address2\": \"\", \"city\": \"Montreal\", \"zip\": \"H2T 1A8\"}, \"destination_location\": {\"id\": 2975422185628, \"country_code\": \"CA\", \"province_code\": \"QC\", \"name\": \"Peter Testometer\", \"address1\": \"3620 Rue Arbour\", \"address2\": \"\", \"city\": \"Qu\\u00e9bec\", \"zip\": \"G2B 4A6\"}}}], \"transactions\": [{\"id\": 4931672866972, \"order_id\": 4009148350620, \"kind\": \"refund\", \"gateway\": \"shopify_payments\", \"status\": \"success\", \"message\": \"Transaction approved\", \"created_at\": \"2021-07-05T06:25:20-04:00\", \"test\": true, \"authorization\": \"re_1J9ozNS0owB3lOujHd3oON7t\", \"location_id\": null, \"user_id\": 73285632156, \"parent_id\": 4931672309916, \"processed_at\": \"2021-07-05T06:25:20-04:00\", \"device_id\": null, \"error_code\": null, \"source_name\": \"1830279\", \"receipt\": {\"id\": \"re_1J9ozNS0owB3lOujHd3oON7t\", \"amount\": 4596, \"balance_transaction\": {\"id\": \"txn_1J9ozNS0owB3lOuj6A6f2SVt\", \"object\": \"balance_transaction\", \"exchange_rate\": null}, \"charge\": {\"id\": \"ch_1J7NIDS0owB3lOujTKxr1mWz\", \"object\": \"charge\", \"amount\": 4596, \"application_fee\": \"fee_1J9oyvS0owB3lOuj87kVjErR\", \"balance_transaction\": \"txn_1J9oyvS0owB3lOuj82shI5rT\", \"captured\": true, \"created\": 1624897601, \"currency\": \"cad\", \"failure_code\": null, \"failure_message\": null, \"fraud_details\": {}, \"livemode\": false, \"metadata\": {\"shop_id\": \"55446438044\", \"shop_name\": \"Frank And Oak Store Dev CAN\", \"payments_charge_id\": \"1849493651612\", \"order_transaction_id\": \"4915025805468\", \"manual_entry\": \"true\", \"order_id\": \"c22114736046236.1\", \"email\": \"peter@mailinator.com\"}, \"outcome\": {\"network_status\": \"approved_by_network\", \"reason\": null, \"risk_level\": \"normal\", \"risk_score\": 53, \"seller_message\": \"Payment complete.\", \"type\": \"authorized\"}, \"paid\": true, \"payment_intent\": \"pi_1J7NICS0owB3lOujM1BmxgyN\", \"payment_method\": \"pm_1J7NICS0owB3lOujCRZHbOo3\", \"payment_method_details\": {\"card\": {\"brand\": \"visa\", \"capture_before\": 1627316801, \"checks\": {\"address_line1_check\": \"pass\", \"address_postal_code_check\": \"pass\", \"cvc_check\": \"pass\"}, \"country\": \"US\", \"description\": null, \"ds_transaction_id\": null, \"exp_month\": 10, \"exp_year\": 2022, \"fingerprint\": \"FtNQzDMF8bVj4BrX\", \"funding\": \"credit\", \"iin\": \"411111\", \"installments\": null, \"issuer\": \"THE CHASE MANHATTAN BANK\", \"last4\": \"1111\", \"moto\": true, \"network\": \"visa\", \"network_transaction_id\": \"1041161205211790\", \"three_d_secure\": null, \"wallet\": null}, \"type\": \"card\"}, \"refunded\": true, \"source\": null, \"status\": \"succeeded\", \"mit_params\": {\"network_transaction_id\": \"1041161205211790\"}}, \"object\": \"refund\", \"reason\": null, \"status\": \"succeeded\", \"created\": 1625480721, \"currency\": \"cad\", \"metadata\": {\"order_transaction_id\": \"4931672866972\", \"payments_refund_id\": \"76215353500\"}, \"payment_method_details\": {\"card\": {\"acquirer_reference_number\": null, \"acquirer_reference_number_status\": \"pending\"}, \"type\": \"card\"}, \"mit_params\": {}}, \"amount\": \"45.96\", \"currency\": \"CAD\", \"admin_graphql_api_id\": \"gid://shopify/OrderTransaction/4931672866972\"}], \"order_adjustments\": [], \"shop_id\": \"frankandoak-shopify-dev-can\"}",
                "attributes": {
                    "ApproximateReceiveCount": "1",
                    "SentTimestamp": "1625480729895",
                    "SenderId": "AROA2CBX66A4P4QTBQED4:frankandoak-receive-shopify-return",
                    "ApproximateFirstReceiveTimestamp": "1625480729902"
                },
                "messageAttributes": {

                },
                "md5OfBody": "3005cde9c38531aede6c008db1e30b6d",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:us-east-1:691607105592:frankandoak-refunds-processor",
                "awsRegion": "us-east-1"
            }
        ]
    }

    newstore_external_orders_url = 'https://frankandoak.x.newstore.net/v0/d/external_orders/11008997'
    newstore_refunds_url = 'https://frankandoak.x.newstore.net/v0/d/orders/6840f40c-65c4-5ff7-a23e-92e0e311091a/refunds'
    shopify_order_url = 'https://frank-and-oak-store-dev.myshopify.com/admin/orders/4009148350620.json'

    newstore_external_orders_url_data = get_mock_data(
        'data/response_newstore_external_orders.json')
    newstore_refunds_url_data = get_mock_data(
        'data/response_newstore_refunds.json')
    shopify_order_data = get_mock_data(
        'data/response_shopify_order.json')

    with requests_mock.Mocker() as mock:
        mock.register_uri('GET', newstore_external_orders_url,
                          text=newstore_external_orders_url_data)
        mock.register_uri('GET', newstore_refunds_url,
                          text=newstore_refunds_url_data)
        mock.register_uri('GET', shopify_order_url,
                          text=shopify_order_data)

        from shopify_process_return.process_refund import handler
        result = handler(event, {})
        LOGGER.info(result)


def get_mock_data(relative_file_path):
    mock_data_file_path = Path(__file__).parent / relative_file_path
    with mock_data_file_path.open() as json_file:
        data = json_file.read()
    return data
