import re
from datetime import datetime


def get_file_name(event_name, country_code, ext, prefix=""):
    """Generate file name like
    (prefix)CCYYMMDD-hhMMssSSS-lowercase_iso2_country_code>-pos-request.csv
    Args:
        event_name (str): Webhook Event Name
        country_code (str): ISO2 country code
        ext (str): File type/extension (without period)
        prefix (str): File name prefix (optional)
    Returns:
        file_name (str): File name
    """
    now = datetime.utcnow()
    ymd, hmsf = now.strftime("%Y%m%d"), now.strftime("%H%M%S%f")
    name = re.sub("[^0-9a-zA-Z]+", "-", event_name).lower()
    return f"{prefix}{ymd}-{hmsf}-{country_code.lower()}-{name}.{ext}"


def get_country_code_from_channel_name(channel_name):
    """ channel_name is newstore order's extended attribute with values (examples):
        CA-QS-SE - for channel advisor orders
        QS-SE - for SFCC orders

    Args:
        channel_name (str): channel name from extended attribte `channel_name`

    Returns:
        (str): Country code, unformatted from attribute
    """
    return channel_name.split("-")[-1]


def get_brand_code_from_channel_name(channel_name):
    """ channel_name is newstore order's extended attribute with values (examples):
        CA-QS-SE - for channel advisor orders
        QS-SE - for SFCC orders

    Args:
        channel_name (str): channel name from extended attribte `channel_name`

    Returns:
        (str): Brand code, unformatted from attribute
    """
    return channel_name.split("-")[-2]
