# -*- coding: utf-8 -*-
# Copyright (C) 2020 NewStore, Inc. All rights reserved.

from base64 import b64decode
from datetime import datetime, timedelta
import json
import logging
import os
import uuid

import boto3
from requests import get, post
from requests.utils import default_user_agent
import segno

'''
Lambda for rendering a template and uploading the result to S3

For use with API Gateway
'''


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def handler(event, context):
    try:
        req_body = json.loads(event['body'])
    except Exception:
        return badRequestError('Bad input')

    try:
        assert 'data' in req_body, 'Missing data'
        assert 'template' in req_body, 'Missing template'
        assert 'Authorization' in event['headers']
        aws_request_id = context.aws_request_id if context.aws_request_id else ''

        resp = gen(req_body['data'], req_body['template'], headers={
            'Content-Type': 'application/json; charset=utf8',
            'Authorization': event['headers']['Authorization'],
            'User-Agent': f'{default_user_agent()} (newstore-integrations:{context.function_name}/{context.function_version})',
            'X-AWS-Request-ID': aws_request_id
        })
    except AssertionError as e:
        return badRequestError(str(e))

    return {
        'isBase64Encoded': False,
        'statusCode': 200,
        'headers': {
            'content-type': 'application/json; charset=utf8'
        },
        'body': json.dumps(resp)
    }


def gen(data: dict, template='sales_receipt', content_type='pdf', style='', locale='en_US', headers={}):
    base_url = f'https://{os.environ["url_api"]}/{os.environ["version"]}'

    templateRequest = get(
        f'{base_url}/d/templates/templates/{template}/localization/{locale}',
        headers=headers
    )

    if not templateRequest.ok:
        raise ValueError(repr(templateRequest))

    qrCodeDataUri = segno.make_qr(f'<open_logistic_order><{data["external_id"]}>').png_data_uri(border=0, scale=3)
    data['qr_code'] = qrCodeDataUri.split('base64,')[1]
    logger.debug(f'Rendering template {template} with data:\n{json.dumps(data, indent=2)}')

    renderRequest = post(
        f'{base_url}/d/templates/templates/{template}/preview',
        json={'data': data, 'template': templateRequest.text, 'content_type': content_type, 'style': style},
        headers=headers
    )

    if not renderRequest.ok:
        raise ValueError(repr(renderRequest))

    rendered = b64decode(renderRequest.text) if content_type == 'pdf' else bytes(renderRequest.text, encoding='utf-8')

    doc_id = uuid.uuid4()
    bucket = os.environ['s3_bucket']
    key = f'{os.environ["s3_key_prefix"]}/{template}-{doc_id}.{content_type}'

    s3 = boto3.resource('s3')
    s3.Bucket(bucket).put_object(
        ACL='public-read',
        Body=rendered,
        Key=key,
        Expires=datetime.now() + timedelta(minutes=5)
    )

    return {
        'url': f'https://s3.amazonaws.com/{bucket}/{key}'
    }


def badRequestError(error_code: str, message='', request_accepted=False) -> dict:
    return {
        'isBase64Encoded': False,
        'statusCode': 400,
        'headers': {
            'content-type': 'application/json; charset=utf8'
        },
        'body': json.dumps({
            'error_code': error_code,
            'message': message,
            'request_accepted': request_accepted
        })
    }
