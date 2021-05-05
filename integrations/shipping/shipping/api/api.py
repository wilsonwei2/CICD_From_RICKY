import json
import logging

from flask import Flask, request, jsonify
from newstore_common.aws import init_root_logger
from newstore_common.newstore.event_stream.utils import with_flask

from shipping.app.quote_service import get_shipping_offer_response
from shipping.app.provider_rates import get_provider_rates
from shipping.app.shipping_options_provider_rates import ProviderRatesRequest

init_root_logger(__name__)
LOGGER = logging.getLogger(__name__)

APP = Flask(__name__)


@APP.before_request
def log_request_info():
    APP.logger.debug("Headers: %s", request.headers)  # pylint: disable=no-member
    APP.logger.debug("Body: %s", request.get_data())  # pylint: disable=no-member


@APP.route("/ping")
def ping():
    return "pong"


@APP.route("/provider_rates", methods=['POST'])
@with_flask(ProviderRatesRequest)
def provider_rates(provider_rates_request: ProviderRatesRequest):
    LOGGER.info(f"Got payload [/provider_rates] {json.dumps(request.json, indent=4)}")
    static_provider_rates = get_provider_rates(provider_rates_request)

    return jsonify(static_provider_rates), 200



@APP.route("/shipping_offers", methods=["POST"])
def shipping_offers():
    order = request.json
    LOGGER.info(f"Got payload [/shipping_offers] {json.dumps(order, indent=4)}")

    result = get_shipping_offer_response(order["shipping_address"]["country_code"],
                                         order["service_level"], order["provider_rate"],
                                         order["ready_by"])

    LOGGER.info(f"Response [/shipping_offers] {json.dumps(result, indent=4)}")
    return jsonify(result), 201
