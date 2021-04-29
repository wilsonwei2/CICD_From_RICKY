import requests
import logging
import json

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class NewStoreConnector():
    host = None
    username = None
    password = None
    token = None


    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password


    def get_token(self):
        if not self.token:
            LOGGER.info(f'Getting token from newstore {self.host}')
            url = 'https://{host}/v0/token'.format(host=self.host)
            headers = {
                'Host': self.host
            }
            form = {
                'grant_type': 'password',
                'username': self.username,
                'password': self.password
            }
            response = requests.post(url=url, headers=headers, data=form)
            _raise_exception_on_error(response)
            self.token = response.json()
            return self.token['access_token']
        LOGGER.info(
            'Token already exists')
        return self.token['access_token']


    def get_order_by_external_id(self, external_id):
        """
        Get Newstore order based on country_code, zip and email,
        country_code can be empty
        """
        url = f'https://{self.host}/v0/d/external_orders/{external_id}' # pylint: disable=logging-too-many-args
        LOGGER.info(f'Getting order values from newstore {url}')
        header = {
            'Authorization': 'Bearer {token}'.format(token=self.get_token())
        }
        response = requests.get(url=url, headers=header)
        _raise_exception_on_error(response)
        return response.json()


    def create_return_for_order(self, order_id, return_data):
        url = f'https://{self.host}/v0/d/orders/{str(order_id)}/returns'
        LOGGER.info(f'Sending return for order {order_id} with:\n {json.dumps(return_data)}')
        header = {
            'Authorization': 'Bearer {token}'.format(token=self.get_token())
        }
        response = requests.post(url=url, headers=header, json=return_data)
        _raise_exception_on_error(response)
        return response.json()


    def get_returns(self, order_id):
        url = f'https://{self.host}/v0/d/orders/{str(order_id)}/returns'
        header = {
            'Authorization': 'Bearer {token}'.format(token=self.get_token())
        }
        response = requests.get(url=url, headers=header)
        _raise_exception_on_error(response)
        return response.json()


    def create_refund_for_order(self, order_id, refund_data):
        url = f'https://{self.host}/v0/d/orders/{str(order_id)}/refunds'
        LOGGER.info(f'Sending refund for order {order_id} with:\n {json.dumps(refund_data)}')
        header = {
            'Authorization': 'Bearer {token}'.format(token=self.get_token())
        }
        response = requests.post(url=url, headers=header, json=refund_data)
        _raise_exception_on_error(response)
        return response.json()


    def get_refunds(self, order_id):
        url = f'https://{self.host}/v0/d/orders/{str(order_id)}/refunds'
        header = {
            'Authorization': 'Bearer {token}'.format(token=self.get_token())
        }
        response = requests.get(url=url, headers=header)
        _raise_exception_on_error(response)
        return response.json()


def _raise_exception_on_error(response):
    try:
        response.raise_for_status()
    except Exception: # pylint: disable=broad-except
        try:
            response_json = response.json()
            LOGGER.error(json.dumps(response_json))
            raise Exception(response_json)
        except Exception:
            response_text = response.text
            LOGGER.error(response_text)
            raise Exception(response_text)
