import json
import logging

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class Error(Exception):
    """Base class for exceptions."""
    # pass


class GatewayError(Error):
    """Exception raised for errors in responses package.

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, status, message): # pylint: disable=super-init-not-called
        self.status = status
        self.message = message

    def __str__(self):
        return json.dumps({
            'statusCode': self.status,
            'body': self.message
        })


async def raise_error_if_exists(response: object) -> dict:
    try:
        response_msg = await response.json()
        response.raise_for_status()
        return response_msg
    except Exception:
        if not response_msg:
            response_msg = response.txt
        else:
            response_msg = json.dumps(response_msg)
        LOGGER.error(response_msg)
        raise GatewayError(response.status, response_msg)
