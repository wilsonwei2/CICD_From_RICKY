import json
import logging

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class Error(Exception):
    """Base class for exceptions."""
    pass

class GatewayError(Error):
    """Exception raised for errors in responses package.

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, status, message):
        self.status = status
        self.message = message

    def __str__(self):
        return json.dumps({
            'statusCode': self.status,
            'body': self.message
            })

async def raise_error_if_exists(response: object, historical=False) -> dict:
    """
    if the historical flag is set to true, then it is possible for Shopify to return an error signalling an
    action has already been taken, but no exception should be raised on account of this error
    """
    try:
        body = await response.json()
    except Exception:
        response.raise_for_status()
    # this conditional is to check specifically for an html response if API call times out
    if not body:
        raise GatewayError(response.status, response.content)
    elif 'errors' in body:
        if historical and 'base' in body['errors'] and 'already' in body['errors']['base'][0]:
            return {'historical': 'true'}
        raise Exception(body['errors'])
    return body
