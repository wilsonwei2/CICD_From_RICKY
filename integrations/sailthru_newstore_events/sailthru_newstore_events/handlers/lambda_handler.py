import boto3
import json


def start_lambda_function(lambda_name, payload={}): # pylint: disable=dangerous-default-value
    session = boto3.session.Session()
    lambda_cli = session.client('lambda', 'us-east-1')
    return lambda_cli.invoke(
        FunctionName=lambda_name,
        InvocationType='Event',
        Payload=json.dumps(payload),
    )
