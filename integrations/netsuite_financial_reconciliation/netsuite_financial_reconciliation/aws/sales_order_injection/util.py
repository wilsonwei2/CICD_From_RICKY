import re

def get_formatted_phone(phone):
    regex = r'^\D?(\d{3})\D?\D?(\d{3})\D?(\d{4})$'
    regex_international = r'^\+?(?:[0-9] ?){6,14}[0-9]$'
    phone = phone if re.match(regex, phone) or re.match(regex_international, phone) else '5555555555'
    if re.match(regex, phone):
        phone = re.sub(regex, r'\1-\2-\3', phone)
    return phone


def get_external_identifiers(external_identifiers, key):
    if external_identifiers:
        for attr in external_identifiers:
            if attr['type'] == key:
                return attr['value']
    return ''


def get_extended_attribute(extended_attributes, key):
    if not extended_attributes or not key:
        return None
    result = next((item['value'] for item in extended_attributes if item['name'] == key), None)
    return result


def require_shipping(item):
    requires_shipping = get_extended_attribute(item.get('extended_attributes'), 'requires_shipping')
    # If it's requires_shipping is None assume that it needs shipping
    return requires_shipping is None or requires_shipping.lower() == 'true'
