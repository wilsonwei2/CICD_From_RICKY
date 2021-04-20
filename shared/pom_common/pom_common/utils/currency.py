from currency_symbols import CurrencySymbols


def get_currency_symbol(currency_code):
    """ Get currency symbol from currency code

    Args:
        currency_code (str): ISO 4217 currency code
    Note:
        https://pypi.org/project/currency-symbols/#description
        https://www.iso.org/iso-4217-currency-codes.html
    """
    return CurrencySymbols.get_symbol(currency_code)
