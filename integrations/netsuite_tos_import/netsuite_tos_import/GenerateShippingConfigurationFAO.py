#Generates the payload to be sent to /v0/i/inventory/transfer_shipping_config


import json

OUTPUT = {
    "transfer_shipping_configuration": [
    ]
}

#It's assumed each location will send to all location. Thus, the hardcoded 'to_location_ids' to '*'
TRANSFER_ELEMENT = {
    "from_location_id": "",
    "to_location_ids": [
        "*"
    ],
    "service_level_ids": [
    ]
}

#Provide the list of stores and the services level supported by each of them
STORES_ALLOW_SERVICE_LEVELS = [{"DIXST": ["STANDARD_UPS"]},
                               {"DONST": ["STANDARD_UPS"]},
                               {"FOYST": ["STANDARD_UPS"]},
                               {"MTLST": ["STANDARD_UPS"]},
                               {"RIDST": ["STANDARD_UPS"]},
                               {"STANST": ["STANDARD_UPS"]},
                               {"STWST": ["STANDARD_UPS"]},
                               {"TECST": ["STANDARD_UPS"]},
                               {"TOST": ["STANDARD_UPS"]},
                               {"VANST": ["STANDARD_UPS"]}]

for store in STORES_ALLOW_SERVICE_LEVELS:
    current_transfer_element = TRANSFER_ELEMENT.copy()
    current_transfer_element['from_location_id'] = list(store.keys())[0]
    current_transfer_element['service_level_ids'] = list(store.values())
    OUTPUT['transfer_shipping_configuration'].append(
        current_transfer_element)

print(json.dumps(OUTPUT))
