import logging

from shipping.app.shipping_options_provider_rates import ProviderRatesRequest

LOGGER = logging.getLogger(__name__)

def get_provider_rates(provider_rates_request: ProviderRatesRequest):
    #country_code = provider_rates_request.shipping_address.country_code
    cur_value = provider_rates_request.bag.products[0].price.currency
    currency = "CAD" if cur_value is None else cur_value

    # based on country code we need to response the respective provider rates
    default_standard_shipping = "STANDARD"
    default_express_shipping = "EXPRESS"
    default_pickuppoint_shipping = "WMS_UPS_PICKUPPOINT"
    default_shiptostore_shipping = "WMS_UPS_SHIPTOSTORE"

    #tnt_standard_shipping = "WMS_TNT_STANDARD"

    standard_shipping = default_standard_shipping
    express_shipping = default_express_shipping
    pickuppoint_shipping = default_pickuppoint_shipping
    shiptostore_shipping = default_shiptostore_shipping

    return {
        "request_id": provider_rates_request.request_id,
        "provider_rates": [
            {
                "id": standard_shipping,
                "service_level_identifier": standard_shipping,
                "provider": "",
                "supported_routes": [
                    "*"
                ],
                "price": {
                    "source": "customization_provider",
                    "amount": 0,
                    "currency": currency
                }
            }, {
                "id": express_shipping,
                "service_level_identifier": express_shipping,
                "provider": "",
                "supported_routes": [
                    "*"
                ],
                "price": {
                    "source": "customization_provider",
                    "amount": 0,
                    "currency": currency
                }
            }, {
                "id": pickuppoint_shipping,
                "service_level_identifier": pickuppoint_shipping,
                "provider": "",
                "supported_routes": [
                    "*"
                ],
                "price": {
                    "source": "customization_provider",
                    "amount": 0,
                    "currency": currency
                }
            }, {
                "id": shiptostore_shipping,
                "service_level_identifier": shiptostore_shipping,
                "provider": "",
                "supported_routes": [
                    "*"
                ],
                "price": {
                    "source": "customization_provider",
                    "amount": 0,
                    "currency": currency
                }
            }
        ]
    }
