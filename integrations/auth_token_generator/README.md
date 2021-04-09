# auth-token-generator


## Functionality
Generation of the auth token for Newstore to avoid other lambda to generate a new auth for each invocation.
Checks the expiry of the token. Also an `EXPIRY_OFFSET` can be configured - the token gets renewed this offset before expiry too ensure the token won't expire during long job runs



### Example of integration to use the lambda to retrieve the token



    def __invoke_shared_token_lambda(self):

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
