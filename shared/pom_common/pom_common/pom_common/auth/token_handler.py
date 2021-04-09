import json
import logging
import os
import boto3

LOGGER = logging.getLogger(__name__)


class Token():
    token = None

    def get_token(self):
        if self.token:
            return self.token

        function_name = os.environ["AUTH_TOKEN_LAMBDA_NAME"]
        payload = {}
        session = boto3.session.Session()
        lambda_cli = session.client("lambda")
        result = lambda_cli.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=bytes(payload),
        )

        LOGGER.info('invoke_auth_token_lambda - auth token - response')
        output = json.loads(result['Payload'].read().decode('utf-8'))['body']['token']

        self.token = output

        return output
