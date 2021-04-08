import logging
import json
import os
import requests
from requests import HTTPError
import re

from opsgenie_api.model import OpsgenieContext, OpsgeniePriority

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig()

class OpsgenieApi:

    API_BASE_URL = "api.opsgenie.com/v2"

    def __init__(self, context: OpsgenieContext):

        self.context = context

    def post_request(self, url, data, headers):

        logger.info(f"POST {url} => {headers} => {json.dumps(data, indent=4)}")
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response

    def get_request(self, url, headers):

        logger.info(f"GET {url} => {headers}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response

    def build_headers(self):

        user_agent = self.context.get_source()
        return {
            "Content-Type": "application/json",
            "tenant": self.context.tenant,
            "X-AWS-Request-ID": self.context.aws_request_id,
            "User-Agent": user_agent,
            "Authorization": f"GenieKey {self.context.get_api_key()}"
        }

    def validate_alias(self, alias: str):

        if len(alias) < 10:
            raise ValueError(f"alias lengt must be greater or equal than 10 => {alias}")

    def purify(self, data: str):

        data = data.strip().lower()
        data = re.sub("[^a-z0-9\s-]", " ", data)
        data = re.sub("\s+", " ", data)
        data = re.sub("\s+", "_", data)
        return data

    def build_response(self, alias: str, response: str):

        return {
            "alias": alias,
            "data": response
        }

    def get_alert(self, alias):

        alias = self.purify(alias)
        self.validate_alias(alias)

        url = f"https://{OpsgenieApi.API_BASE_URL}/alerts/{alias}?identifierType=alias"
        response = self.post_request(url,
            {
                "source": self.context.get_source()
            },
            self.build_headers())

        return self.build_response(alias, response.json())

    def close_alert(self, alias:str):

        alias = self.purify(alias)
        self.validate_alias(alias)

        url = f"https://{OpsgenieApi.API_BASE_URL}/alerts/{alias}/close?identifierType=alias"
        response = self.post_request(url,
            {
                "source": self.context.get_source()
            },
            self.build_headers())
        return self.build_response(alias, response.json())

    def build_alias(self, alert_type:str, entity_id:str):
        alias = f"{alert_type} {entity_id}"
        alias = self.purify(alias)
        self.validate_alias(alias)
        return alias

    def publish_alert(self, alert_type:str, entity_id:str, message:str, description:str=None, priority=OpsgeniePriority.Moderate, tags=None):

        alias = self.build_alias(alert_type, entity_id)

        if not message:
            raise TypeError("message are required arguments")

        url = f"https://{OpsgenieApi.API_BASE_URL}/alerts"

        data = {
            "alias": alias,
            "message": message,
            "description": description,
            "responders": self.context.get_responders(),
            "visibleTo": self.context.get_visible_to(),
            "actions": self.context.get_actions(),
            "tags": [
                self.context.get_tenant(),
                priority.name.lower(),
                self.context.get_stage()
            ]+tags,
            "details": {
                "tenant": self.context.get_tenant(),
                "stage": self.context.get_stage(),
                "function_name": self.context.get_function_name(),
                "function_version": self.context.get_function_version(),
                "aws_request_id": self.context.get_aws_request_id(),
                "integrator_name": self.context.get_integrator_name(),
                "entity_id": entity_id,
                "alert_type": alert_type
            },
            "priority": priority.value
        }

        response = self.post_request(url, data, self.build_headers())
        return self.build_response(alias, response.json())
