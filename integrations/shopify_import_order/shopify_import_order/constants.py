SHIPPING_OPTIONS = [
    {
        'service_level_identifier': 'CUSTOM_GROUND',
        'shipping_carrier': 'CUSTOM_CARRIER',
        'shipping_type': 'traditional_carrier'
    }
]

## THESE values are not finalized, The mapping provided in the requirements document and
## Shopify are different.
## Need to keep in mind, when making a release.
SHIPPING_OPTIONS_MAPPED = {
    ## Remember that these keys are dependent on the Shopify Keys in Shipping lines.
    'usps': {
        'first class package international':'INTERNATIONAL',
        'free standard shipping (5-7 business days)':'STANDARD',
        'worldwide':'INTERNATIONAL',
        'priority mail':'FIRST_CLASS', ## NOT in requirement but shopify has it
        'priority':'FIRST_CLASS',
        'priority mail express':'FIRST_CLASS',
        'USPS Global Priority (7-9 business days)':'USPS_PRIORITY',
    },## keys has to be in smaller case.
    'fedex': {
        'fedex expedited':'EXPEDITED',
        'fedex ground':'GROUND',
        'fedex ground(5-7 business days)':'GROUND',
        'fedex priority':'PRIORITY',
        'fedex priority(2-4 business days)':'PRIORITY',
        'fedex expedited (1-3 business days)': 'EXPEDITED'
    },
    'shopify': {
        'free exchange shipping': 'EXCHANGE_CUSTOM',
        'ups ground (2-5 days)': 'UPS_GROUND',
        'USPS Global Priority (7-9 business days)':'USPS_PRIORITY',
        'first class package international':'INTERNATIONAL',
        'free standard shipping (5-7 business days)':'STANDARD',
        'worldwide':'INTERNATIONAL',
        'priority mail':'FIRST_CLASS',
        'priority':'FIRST_CLASS',
        'priority mail express':'FIRST_CLASS'
    },
    'allSource': {
        'first' : 'FIRST_CLASS',
        'feathers/pins only' : 'FIRST_CLASS',
        'prioritymailexpressinternational' : 'EXPRESS_INTER',
        'priorityexpress' : 'EXPRESS',
        'firstpackage' : 'FIRST_CLASS_PKG',
        'priority' : 'PRIORITY',
        'firstclasspackageinternationalservice' : 'FIRST_CLASS_INTER',
        'prioritymailinternational' : 'PRIORITY_INTER',
        'usps global priority (7-9 business days)' : 'PRIORITY_INTER',
        'fedex ground' : 'GROUND',
        'zero charge free ship (fedex ground)' : 'GROUND',
        'free standard shipping (5-7 business days)' : 'GROUND',
        'ups ground (2-5 days)' : 'GROUND',
        'fedex ground (5-7 business days)' : 'GROUND',
        'returnly_free_exchange_shipping' : 'GROUND',
        'custom' : 'GROUND',
        'fedex priority' : '2_DAY',
        'ups expedited (1-3 days)' : '2_DAY',
        'fedex expedited (1-3 business days)' : '2_DAY',
        'fedex priority (2-4 days)' : '2_DAY',
        'fedex priority (2-4 business days)' : '2_DAY',
        'fedex ground with insurance' : 'GROUND',
        'usps priority international with insurance' : 'PRIORITY_INTER',
        'free standard shipping with insurance' : 'GROUND',
        'free shipping with insurance surcharge' : 'GROUND'
    }
}

CHANNEL_TYPES = [
    'web',
    'mobile'
]
