import logging
import json

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(10)


def test_authorization():
    from historical_orders_adapter.lambdas.handler import handle

    request_event = {
        "resource": "/financial_instruments",
        "path": "/financial_instruments",
        "httpMethod": "POST",
        "headers": {
            "accept-encoding": "gzip",
            "CloudFront-Forwarded-Proto": "https",
            "CloudFront-Is-Desktop-Viewer": "true",
            "CloudFront-Is-Mobile-Viewer": "false",
            "CloudFront-Is-SmartTV-Viewer": "false",
            "CloudFront-Is-Tablet-Viewer": "false",
            "CloudFront-Viewer-Country": "US",
            "Host": "0jufcsj0e9.execute-api.us-east-1.amazonaws.com",
            "User-Agent": "Go-http-client/2.0",
            "Via": "2.0 25e2963eb5d8a7965bc8b98c455aab49.cloudfront.net (CloudFront)",
            "X-Amz-Cf-Id": "RMBKxdhFi8jC6jOVPIUjyS5T1AGQa3BlgSCyrxe92YXeoBF-B-8Osw==",
            "X-Amzn-Trace-Id": "Root=1-5f899ebb-22d0819e1f36d213038a71f5",
            "X-Forwarded-For": "54.205.10.147, 130.176.134.146",
            "X-Forwarded-Port": "443",
            "X-Forwarded-Proto": "https"
        },
        "multiValueHeaders": {
            "accept-encoding": [
                "gzip"
            ],
            "CloudFront-Forwarded-Proto": [
                "https"
            ],
            "CloudFront-Is-Desktop-Viewer": [
                "true"
            ],
            "CloudFront-Is-Mobile-Viewer": [
                "false"
            ],
            "CloudFront-Is-SmartTV-Viewer": [
                "false"
            ],
            "CloudFront-Is-Tablet-Viewer": [
                "false"
            ],
            "CloudFront-Viewer-Country": [
                "US"
            ],
            "Host": [
                "0jufcsj0e9.execute-api.us-east-1.amazonaws.com"
            ],
            "User-Agent": [
                "Go-http-client/2.0"
            ],
            "Via": [
                "2.0 25e2963eb5d8a7965bc8b98c455aab49.cloudfront.net (CloudFront)"
            ],
            "X-Amz-Cf-Id": [
                "RMBKxdhFi8jC6jOVPIUjyS5T1AGQa3BlgSCyrxe92YXeoBF-B-8Osw=="
            ],
            "X-Amzn-Trace-Id": [
                "Root=1-5f899ebb-22d0819e1f36d213038a71f5"
            ],
            "X-Forwarded-For": [
                "54.205.10.147, 130.176.134.146"
            ],
            "X-Forwarded-Port": [
                "443"
            ],
            "X-Forwarded-Proto": [
                "https"
            ]
        },
        "queryStringParameters": "None",
        "multiValueQueryStringParameters": "None",
        "pathParameters": "None",
        "stageVariables": "None",
        "requestContext": {
            "resourceId": "vytcse",
            "resourcePath": "/financial_instruments",
            "httpMethod": "POST",
            "extendedRequestId": "UgW9PHwsoAMFyag=",
            "requestTime": "16/Oct/2020:13:23:07 +0000",
            "path": "/x/financial_instruments",
            "accountId": "104965260512",
            "protocol": "HTTP/1.1",
            "stage": "x",
            "domainPrefix": "0jufcsj0e9",
            "requestTimeEpoch": 1602854587049,
            "requestId": "e3932f70-961c-46e0-a67b-ff5bfa531e6e",
            "identity": {
                "cognitoIdentityPoolId": "None",
                "accountId": "None",
                "cognitoIdentityId": "None",
                "caller": "None",
                "sourceIp": "54.205.10.147",
                "principalOrgId": "None",
                "accessKey": "None",
                "cognitoAuthenticationType": "None",
                "cognitoAuthenticationProvider": "None",
                "userArn": "None",
                "userAgent": "Go-http-client/2.0",
                "user": "None"
            },
            "domainName": "0jufcsj0e9.execute-api.us-east-1.amazonaws.com",
            "apiId": "0jufcsj0e9"
        },
        "body": "{\"account_id\":\"a114c7ee-06c2-5752-ae58-1bc67eaf8e01\",\"transactions\":[],\"idempotency_key\":\"authorized.852602688402658J-a114c7ee-06c2-5752-ae58-1bc67eaf8e01\",\"arguments\":{\"instrument\":{\"type\":\"authorized\",\"identifier\":\"852602688402658J\"},\"amount\":1000,\"currency\":\"SEK\",\"payment_method\":\"CREDIT-CARD\"},\"metadata\":{\"cc_number\":\"\",\"cc_type\":\"\",\"order_id\":\"DEV-2243580\",\"processed_at\":\"2020-10-14T15:13:21\",\"provider_account_id\":\"BRD-EMEA-PUKALANI-ECO\"}}",
        "isBase64Encoded": False
    }

    request_event_body = json.loads(request_event['body'])
    logging.info(f"Event Body {request_event_body}")

    result = handle(request_event, {})
    result_body = json.loads(result['body'])
    assert result['statusCode'] == 200
    assert request_event_body['arguments']['amount'] == result_body[0]['capture_amount']
    assert request_event_body['arguments']['currency'] == result_body[0]['currency']

    # On the first authorization there shouldn't be any trasactions present.
    assert len(request_event_body['transactions']) == 0

    assert result_body[0]['refund_amount'] == 0

    logging.info(f"Event Result {result}")


def test_capture():
    from historical_orders_adapter.lambdas.handler import handle

    request_event = {
        "resource": "/financial_instruments/{financial_instrument_id}/_capture",
        "path": "/financial_instruments/authorized.1252602688402694J-70958178-0e60-511a-9b46-64ccf740f3a5/_capture",
        "httpMethod": "POST",
        "headers": {
            "accept-encoding": "gzip",
            "CloudFront-Forwarded-Proto": "https",
            "CloudFront-Is-Desktop-Viewer": "true",
            "CloudFront-Is-Mobile-Viewer": "false",
            "CloudFront-Is-SmartTV-Viewer": "false",
            "CloudFront-Is-Tablet-Viewer": "false",
            "CloudFront-Viewer-Country": "US",
            "content-type": "application/json",
            "Host": "0jufcsj0e9.execute-api.us-east-1.amazonaws.com",
            "User-Agent": "Go-http-client/2.0",
            "Via": "2.0 2cfc0bae5f623e4a6a6bc0939f1d71c8.cloudfront.net (CloudFront)",
            "X-Amz-Cf-Id": "yPMYn8p828Qp3ZVvAEUKZvNV6lAtfWZFaIiPz-PIoFTDYTDgkF_Lhg==",
            "X-Amzn-Trace-Id": "Root=1-5f986145-17066592429a11c82df4ed1a",
            "X-Forwarded-For": "54.205.10.147, 130.176.134.144",
            "X-Forwarded-Port": "443",
            "X-Forwarded-Proto": "https"
        },
        "multiValueHeaders": {
            "accept-encoding": [
                "gzip"
            ],
            "CloudFront-Forwarded-Proto": [
                "https"
            ],
            "CloudFront-Is-Desktop-Viewer": [
                "true"
            ],
            "CloudFront-Is-Mobile-Viewer": [
                "false"
            ],
            "CloudFront-Is-SmartTV-Viewer": [
                "false"
            ],
            "CloudFront-Is-Tablet-Viewer": [
                "false"
            ],
            "CloudFront-Viewer-Country": [
                "US"
            ],
            "content-type": [
                "application/json"
            ],
            "Host": [
                "0jufcsj0e9.execute-api.us-east-1.amazonaws.com"
            ],
            "User-Agent": [
                "Go-http-client/2.0"
            ],
            "Via": [
                "2.0 2cfc0bae5f623e4a6a6bc0939f1d71c8.cloudfront.net (CloudFront)"
            ],
            "X-Amz-Cf-Id": [
                "yPMYn8p828Qp3ZVvAEUKZvNV6lAtfWZFaIiPz-PIoFTDYTDgkF_Lhg=="
            ],
            "X-Amzn-Trace-Id": [
                "Root=1-5f986145-17066592429a11c82df4ed1a"
            ],
            "X-Forwarded-For": [
                "54.205.10.147, 130.176.134.144"
            ],
            "X-Forwarded-Port": [
                "443"
            ],
            "X-Forwarded-Proto": [
                "https"
            ]
        },
        "queryStringParameters": "None",
        "multiValueQueryStringParameters": "None",
        "pathParameters": {
            "financial_instrument_id": "authorized.1252602688402694J-70958178-0e60-511a-9b46-64ccf740f3a5"
        },
        "stageVariables": "None",
        "requestContext": {
            "resourceId": "2uguk6",
            "resourcePath": "/financial_instruments/{financial_instrument_id}/_capture",
            "httpMethod": "POST",
            "extendedRequestId": "VFQi3GiKoAMFXVg=",
            "requestTime": "27/Oct/2020:18:04:53 +0000",
            "path": "/x/financial_instruments/authorized.1252602688402694J-70958178-0e60-511a-9b46-64ccf740f3a5/_capture",
            "accountId": "104965260512",
            "protocol": "HTTP/1.1",
            "stage": "x",
            "domainPrefix": "0jufcsj0e9",
            "requestTimeEpoch": 1603821893480,
            "requestId": "0fc48c5d-78f2-4592-bea2-1c9e335f77cc",
            "identity": {
                "cognitoIdentityPoolId": "None",
                "accountId": "None",
                "cognitoIdentityId": "None",
                "caller": "None",
                "sourceIp": "54.205.10.147",
                "principalOrgId": "None",
                "accessKey": "None",
                "cognitoAuthenticationType": "None",
                "cognitoAuthenticationProvider": "None",
                "userArn": "None",
                "userAgent": "Go-http-client/2.0",
                "user": "None"
            },
            "domainName": "0jufcsj0e9.execute-api.us-east-1.amazonaws.com",
            "apiId": "0jufcsj0e9"
        },
        "body": "{\"account_id\":\"70958178-0e60-511a-9b46-64ccf740f3a5\",\"transactions\":[{\"payment_method\":\"credit_card\",\"payment_wallet\":\"Apple Pay\",\"transaction_id\":\"authorized.1252602688402694J-70958178-0e60-511a-9b46-64ccf740f3a5\",\"instrument_id\":\"authorized.1252602688402694J-70958178-0e60-511a-9b46-64ccf740f3a5\",\"capture_amount\":634,\"refund_amount\":0,\"currency\":\"SEK\",\"metadata\":{\"essential\":{\"instrument_metadata\":{\"card_brand\":\"Visa\",\"card_expiration_month\":11,\"card_expiration_year\":2030,\"card_last4\":\"0\",\"payer_email\":\"matias.sanchez@positiveminds.io\"}}},\"reason\":\"authorization\",\"created_at\":\"2020-10-27T15:13:21Z\",\"processed_at\":\"2020-10-27T15:13:21Z\"}],\"idempotency_key\":\"8863163c-cceb-412f-8b0d-d354844ea7bc\",\"arguments\":{\"amount\":634,\"currency\":\"SEK\"},\"metadata\":{\"order_id\":\"DEV-3443598\",\"order_number\":\"BRD100000404\",\"processed_at\":\"2020-10-27T15:13:21\",\"provider_account_id\":\"BRD-EMEA-PUKALANI-ECO\"}}",
        "isBase64Encoded": False
    }

    request_event_body = json.loads(request_event['body'])
    logging.info(f"Event Body {request_event_body}")

    result = handle(request_event, {})
    result_body = json.loads(result['body'])
    assert result['statusCode'] == 200
    assert request_event_body['arguments']['amount'] * - \
        1 == result_body[0]['capture_amount']

    # On the carpture. there should be one transaction. That is, the Authorization
    assert len(request_event_body['transactions']) == 1

    assert request_event_body['arguments']['currency'] == result_body[0]['currency']

    logging.info(f"Event Result {result}")


def test_revoke():
    from historical_orders_adapter.lambdas.handler import handle

    request_event = {
        "resource": "/financial_instruments/{financial_instrument_id}/_revoke",
        "path": "/financial_instruments/authorized.1252602688402694J-f31d0c4f-e7bc-5897-8c5f-47db98bd26d4/_revoke",
        "httpMethod": "POST",
        "headers": {
            "accept-encoding": "gzip",
            "CloudFront-Forwarded-Proto": "https",
            "CloudFront-Is-Desktop-Viewer": "true",
            "CloudFront-Is-Mobile-Viewer": "false",
            "CloudFront-Is-SmartTV-Viewer": "false",
            "CloudFront-Is-Tablet-Viewer": "false",
            "CloudFront-Viewer-Country": "US",
            "content-type": "application/json",
            "Host": "0jufcsj0e9.execute-api.us-east-1.amazonaws.com",
            "User-Agent": "Go-http-client/2.0",
            "Via": "2.0 6bcd5dba28bbc19dcd3f4c10e978e8ef.cloudfront.net (CloudFront)",
            "X-Amz-Cf-Id": "qWBSOxQXcQl8ZE9oDG7QDwsH4BkNFxh-2JFxvhw9xPKb_FYxHTWpug==",
            "X-Amzn-Trace-Id": "Root=1-5f9867b9-1975eaed641e91de64a7fdee",
            "X-Forwarded-For": "54.205.10.147, 130.176.134.85",
            "X-Forwarded-Port": "443",
            "X-Forwarded-Proto": "https"
        },
        "multiValueHeaders": {
            "accept-encoding": [
                "gzip"
            ],
            "CloudFront-Forwarded-Proto": [
                "https"
            ],
            "CloudFront-Is-Desktop-Viewer": [
                "true"
            ],
            "CloudFront-Is-Mobile-Viewer": [
                "false"
            ],
            "CloudFront-Is-SmartTV-Viewer": [
                "false"
            ],
            "CloudFront-Is-Tablet-Viewer": [
                "false"
            ],
            "CloudFront-Viewer-Country": [
                "US"
            ],
            "content-type": [
                "application/json"
            ],
            "Host": [
                "0jufcsj0e9.execute-api.us-east-1.amazonaws.com"
            ],
            "User-Agent": [
                "Go-http-client/2.0"
            ],
            "Via": [
                "2.0 6bcd5dba28bbc19dcd3f4c10e978e8ef.cloudfront.net (CloudFront)"
            ],
            "X-Amz-Cf-Id": [
                "qWBSOxQXcQl8ZE9oDG7QDwsH4BkNFxh-2JFxvhw9xPKb_FYxHTWpug=="
            ],
            "X-Amzn-Trace-Id": [
                "Root=1-5f9867b9-1975eaed641e91de64a7fdee"
            ],
            "X-Forwarded-For": [
                "54.205.10.147, 130.176.134.85"
            ],
            "X-Forwarded-Port": [
                "443"
            ],
            "X-Forwarded-Proto": [
                "https"
            ]
        },
        "queryStringParameters": "None",
        "multiValueQueryStringParameters": "None",
        "pathParameters": {
            "financial_instrument_id": "authorized.1252602688402694J-f31d0c4f-e7bc-5897-8c5f-47db98bd26d4"
        },
        "stageVariables": "None",
        "requestContext": {
            "resourceId": "qf36zl",
            "resourcePath": "/financial_instruments/{financial_instrument_id}/_revoke",
            "httpMethod": "POST",
            "extendedRequestId": "VFUk7FC7IAMFm7A=",
            "requestTime": "27/Oct/2020:18:32:25 +0000",
            "path": "/x/financial_instruments/authorized.1252602688402694J-f31d0c4f-e7bc-5897-8c5f-47db98bd26d4/_revoke",
            "accountId": "104965260512",
            "protocol": "HTTP/1.1",
            "stage": "x",
            "domainPrefix": "0jufcsj0e9",
            "requestTimeEpoch": 1603823545019,
            "requestId": "ffbcda21-180d-4805-9690-9299b95b4dfc",
            "identity": {
                "cognitoIdentityPoolId": "None",
                "accountId": "None",
                "cognitoIdentityId": "None",
                "caller": "None",
                "sourceIp": "54.205.10.147",
                "principalOrgId": "None",
                "accessKey": "None",
                "cognitoAuthenticationType": "None",
                "cognitoAuthenticationProvider": "None",
                "userArn": "None",
                "userAgent": "Go-http-client/2.0",
                "user": "None"
            },
            "domainName": "0jufcsj0e9.execute-api.us-east-1.amazonaws.com",
            "apiId": "0jufcsj0e9"
        },
        "body": "{\"account_id\":\"f31d0c4f-e7bc-5897-8c5f-47db98bd26d4\",\"transactions\":[{\"payment_method\":\"credit_card\",\"payment_wallet\":\"Apple Pay\",\"transaction_id\":\"authorized.1252602688402694J-f31d0c4f-e7bc-5897-8c5f-47db98bd26d4\",\"instrument_id\":\"authorized.1252602688402694J-f31d0c4f-e7bc-5897-8c5f-47db98bd26d4\",\"capture_amount\":634,\"refund_amount\":0,\"currency\":\"SEK\",\"metadata\":{\"essential\":{\"instrument_metadata\":{\"card_brand\":\"Visa\",\"card_expiration_month\":11,\"card_expiration_year\":2030,\"card_last4\":\"0\",\"payer_email\":\"matias.sanchez@positiveminds.io\"}}},\"reason\":\"authorization\",\"created_at\":\"2020-10-27T15:13:21Z\",\"processed_at\":\"2020-10-27T15:13:21Z\"}],\"idempotency_key\":\"reduction-revoke-f31d0c4f-e7bc-5897-8c5f-47db98bd26d4\",\"arguments\":{\"amount\":634,\"currency\":\"SEK\"},\"metadata\":{\"order_id\":\"DEV-3443002\",\"processed_at\":\"2020-10-27T15:13:21\",\"provider_account_id\":\"BRD-EMEA-PUKALANI-ECO\"}}",
        "isBase64Encoded": False
    }

    request_event_body = json.loads(request_event['body'])
    logging.info(f"Event Body {request_event_body}")

    result = handle(request_event, {})
    result_body = json.loads(result['body'])
    assert result['statusCode'] == 200
    assert request_event_body['arguments']['amount'] * - \
        1 == result_body[0]['capture_amount']
    assert request_event_body['arguments']['currency'] == result_body[0]['currency']

    # On the revoke, there should be more that 1 trasactions. That is, at least an Authorization. We can have a capture, maybe even multiple refunds.
    assert len(request_event_body['transactions']) > 0

    assert result_body[0]['refund_amount'] == 0

    logging.info(f"Event Result {result}")


def test_refund():
    from historical_orders_adapter.lambdas.handler import handle

    request_event = {
        "resource": "/financial_instruments/{financial_instrument_id}/_refund",
        "path": "/financial_instruments/authorized.1252602688402694J-c1096688-699d-5c24-af6a-f7570f969c58/_refund",
        "httpMethod": "POST",
        "headers": {
            "accept-encoding": "gzip",
            "CloudFront-Forwarded-Proto": "https",
            "CloudFront-Is-Desktop-Viewer": "true",
            "CloudFront-Is-Mobile-Viewer": "false",
            "CloudFront-Is-SmartTV-Viewer": "false",
            "CloudFront-Is-Tablet-Viewer": "false",
            "CloudFront-Viewer-Country": "US",
            "content-type": "application/json",
            "Host": "0jufcsj0e9.execute-api.us-east-1.amazonaws.com",
            "User-Agent": "Go-http-client/2.0",
            "Via": "2.0 9317f1a4c7320bdeb8f38066b985748b.cloudfront.net (CloudFront)",
            "X-Amz-Cf-Id": "lCljhlYyEI30i9Bl0scSkHUE8qiAp_-lBegjaVjj7hAC626272ZzcQ==",
            "X-Amzn-Trace-Id": "Root=1-5f986b41-3ae140ff4df711b2172291a1",
            "X-Forwarded-For": "54.205.10.147, 130.176.134.68",
            "X-Forwarded-Port": "443",
            "X-Forwarded-Proto": "https"
        },
        "multiValueHeaders": {
            "accept-encoding": [
                "gzip"
            ],
            "CloudFront-Forwarded-Proto": [
                "https"
            ],
            "CloudFront-Is-Desktop-Viewer": [
                "true"
            ],
            "CloudFront-Is-Mobile-Viewer": [
                "false"
            ],
            "CloudFront-Is-SmartTV-Viewer": [
                "false"
            ],
            "CloudFront-Is-Tablet-Viewer": [
                "false"
            ],
            "CloudFront-Viewer-Country": [
                "US"
            ],
            "content-type": [
                "application/json"
            ],
            "Host": [
                "0jufcsj0e9.execute-api.us-east-1.amazonaws.com"
            ],
            "User-Agent": [
                "Go-http-client/2.0"
            ],
            "Via": [
                "2.0 9317f1a4c7320bdeb8f38066b985748b.cloudfront.net (CloudFront)"
            ],
            "X-Amz-Cf-Id": [
                "lCljhlYyEI30i9Bl0scSkHUE8qiAp_-lBegjaVjj7hAC626272ZzcQ=="
            ],
            "X-Amzn-Trace-Id": [
                "Root=1-5f986b41-3ae140ff4df711b2172291a1"
            ],
            "X-Forwarded-For": [
                "54.205.10.147, 130.176.134.68"
            ],
            "X-Forwarded-Port": [
                "443"
            ],
            "X-Forwarded-Proto": [
                "https"
            ]
        },
        "queryStringParameters": "None",
        "multiValueQueryStringParameters": "None",
        "pathParameters": {
            "financial_instrument_id": "authorized.1252602688402694J-c1096688-699d-5c24-af6a-f7570f969c58"
        },
        "stageVariables": "None",
        "requestContext": {
            "resourceId": "t9zqlo",
            "resourcePath": "/financial_instruments/{financial_instrument_id}/_refund",
            "httpMethod": "POST",
            "extendedRequestId": "VFWyMEJJIAMF6ZQ=",
            "requestTime": "27/Oct/2020:18:47:29 +0000",
            "path": "/x/financial_instruments/authorized.1252602688402694J-c1096688-699d-5c24-af6a-f7570f969c58/_refund",
            "accountId": "104965260512",
            "protocol": "HTTP/1.1",
            "stage": "x",
            "domainPrefix": "0jufcsj0e9",
            "requestTimeEpoch": 1603824449196,
            "requestId": "4d0e1e61-730e-41ee-8972-b1e23e095885",
            "identity": {
                "cognitoIdentityPoolId": "None",
                "accountId": "None",
                "cognitoIdentityId": "None",
                "caller": "None",
                "sourceIp": "54.205.10.147",
                "principalOrgId": "None",
                "accessKey": "None",
                "cognitoAuthenticationType": "None",
                "cognitoAuthenticationProvider": "None",
                "userArn": "None",
                "userAgent": "Go-http-client/2.0",
                "user": "None"
            },
            "domainName": "0jufcsj0e9.execute-api.us-east-1.amazonaws.com",
            "apiId": "0jufcsj0e9"
        },
        "body": "{\"account_id\":\"c1096688-699d-5c24-af6a-f7570f969c58\",\"transactions\":[{\"payment_method\":\"credit_card\",\"payment_wallet\":\"Apple Pay\",\"transaction_id\":\"authorized.1252602688402694J-c1096688-699d-5c24-af6a-f7570f969c58-capture\",\"instrument_id\":\"authorized.1252602688402694J-c1096688-699d-5c24-af6a-f7570f969c58\",\"capture_amount\":-634,\"refund_amount\":634,\"currency\":\"SEK\",\"metadata\":null,\"reason\":\"capture\",\"created_at\":\"2020-10-27T18:47:03Z\",\"processed_at\":\"2020-10-27T18:47:03Z\"},{\"payment_method\":\"credit_card\",\"payment_wallet\":\"Apple Pay\",\"transaction_id\":\"authorized.1252602688402694J-c1096688-699d-5c24-af6a-f7570f969c58\",\"instrument_id\":\"authorized.1252602688402694J-c1096688-699d-5c24-af6a-f7570f969c58\",\"capture_amount\":634,\"refund_amount\":0,\"currency\":\"SEK\",\"metadata\":{\"essential\":{\"instrument_metadata\":{\"card_brand\":\"Visa\",\"card_expiration_month\":11,\"card_expiration_year\":2030,\"card_last4\":\"0\",\"payer_email\":\"matias.sanchez@positiveminds.io\"}}},\"reason\":\"authorization\",\"created_at\":\"2020-10-27T15:13:21Z\",\"processed_at\":\"2020-10-27T15:13:21Z\"}],\"idempotency_key\":\"140cf8b4-ec01-4dfe-9db3-163fd3edb117\",\"arguments\":{\"amount\":634,\"currency\":\"SEK\"},\"metadata\":{\"order_id\":\"DEV-3443004\",\"original_operation\":\"refund\",\"processed_at\":\"2020-10-27T15:13:21\",\"provider_account_id\":\"BRD-EMEA-PUKALANI-ECO\"}}",
        "isBase64Encoded": False
    }

    request_event_body = json.loads(request_event['body'])
    logging.info(f"Event Body {request_event_body}")

    result = handle(request_event, {})
    result_body = json.loads(result['body'])
    assert result['statusCode'] == 200
    assert request_event_body['arguments']['amount'] * - \
        1 == result_body[0]['refund_amount']
    assert request_event_body['arguments']['currency'] == result_body[0]['currency']

    # On the refund, there should be more that 2 trasactions. That is, at least an Authorization and Capture. We could have many refunds.
    assert len(request_event_body['transactions']) > 1

    assert result_body[0]['capture_amount'] == 0

    logging.info(f"Event Result {result}")
