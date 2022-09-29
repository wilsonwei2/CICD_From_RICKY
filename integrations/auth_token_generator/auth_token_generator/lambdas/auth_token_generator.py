import os
import logging
import json
import time
import jwt
import base64
import boto3
from auth_token_generator.utils import Utils
from botocore.exceptions import ClientError
from newstore_common.aws import init_root_logger
from newstore_adapter.connector import NewStoreConnector

init_root_logger(__name__)
LOGGER = logging.getLogger(__name__)

TENANT = os.environ["TENANT"]
STAGE = os.environ["STAGE"]

TOKEN = None
COUNTER = 0


def handler(event, context):
    LOGGER.info(f"Event: {json.dumps(event, indent=2)}")

    global TOKEN # pylint: disable=global-statement
    global COUNTER # pylint: disable=global-statement
    COUNTER = COUNTER + 1

    try:
        TOKEN = get_token(context)
        LOGGER.debug(f"current token: {TOKEN}")
        LOGGER.info(f"no of invocation with the same token: {COUNTER}")

    except Exception as ex: # pylint: disable=broad-except
        LOGGER.info(ex)
        LOGGER.critical("Error during token generation.")

    return {
        "isBase64Encoded": False,
        "statusCode": 200,
        "body": TOKEN
    }


def get_token(context):
    global TOKEN # pylint: disable=global-statement
    global COUNTER # pylint: disable=global-statement

    force_token_generation = os.environ.get("FORCE", False)

    is_expired = False
    if TOKEN:
        expiry_offset = int(os.environ.get("EXPIRY_OFFSET", "0"))

        token_exp = get_token_expiry(TOKEN["access_token"])
        is_expired = int(time.time()) >= (token_exp - expiry_offset)

    if not TOKEN or force_token_generation == "1" or is_expired:

        LOGGER.info(f"requesting new access token (forced? {force_token_generation}, expired? {is_expired})")

        credentials = get_credentials()

        newstore_config = Utils.get_instance().get_newstore_config()
        ns_handler = NewStoreConnector(
            tenant=newstore_config["tenant"],
            context=context,
            host=newstore_config["host"],
            username=credentials["username"],
            password=credentials["password"]
        )

        COUNTER = 0
        auth = ns_handler.newstore_adapter.get_api_auth()
        result = auth.auth_request()
        result["expires_at"] = get_token_expiry(result["access_token"])
        return result

    LOGGER.info(f'Token already exists')
    return TOKEN


def get_credentials():
    """ Get Auth Credentials from Secrets Manager """
    try:
        secret_name = os.environ["SECRET_NAME_NEWSTORE_API_USER"]
        region = os.environ["REGION"]

        session = boto3.session.Session()
        client = session.client(
            service_name="secretsmanager",
            region_name=region
        )

        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )

        secret = ""
        if "SecretString" in get_secret_value_response:
            secret = get_secret_value_response["SecretString"]
        else:
            secret = base64.b64decode(
                get_secret_value_response["SecretBinary"])

        return json.loads(secret)
    except KeyError as error:
        raise RuntimeError("get_credentials: Missing environ variable") from error
    except ClientError as error:
        raise RuntimeError("get_credentials: Cannot load values from Secrets") from error


def get_token_expiry(token):
    return jwt.decode(token, options={
        "verify_signature": False,
        "verify_exp": False,
    })["exp"]
