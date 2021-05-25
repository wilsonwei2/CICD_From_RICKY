import logging
import json
import os
from sailthru.sailthru_client import SailthruClient
from .utils import get_param

# loggers
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

# invokes the sailthru send api and prints the response.
def handler(event, context): # pylint: disable=unused-argument
    json_data = json.loads(event['body'])
    LOGGER.info(f'json_data {json.dumps(json_data)}')

    # Get the env variables data
    credentials = get_param(os.environ.get('SAILTHRU_CREDS_PARAM', 'sailthru_credentials'))
    # many countries will use EU credentials, so use EU as default when specific country isn't mapped in param
    creds_by_country = credentials[json_data['template'].split(' ')[0]]
    api_key = creds_by_country['id']
    api_secret = creds_by_country['secret']

    # Sailthru client & send api calls
    sailthru_client = SailthruClient(api_key, api_secret)
    response = sailthru_client.api_post("send", json_data)
    reponse_object = {}

    if response.is_ok():
        LOGGER.info(f'success response {response.get_body()}')
        reponse_object['statusCode'] = str(response.get_status_code())
        reponse_object['body'] = str(response.get_body())
        return reponse_object
    LOGGER.info(f'error response {response.get_body()}')
    reponse_object['statusCode'] = str(response.get_status_code())
    reponse_object['body'] = str(response.get_body())
    return reponse_object
