"""
Transformer.py

Transformer for converting the CSV data to price import job payload for import jobs.

@author Aditya Kasturi akasturi@newstore.com
"""
import csv
import logging

from datetime import datetime

LOGGER = logging.getLogger()

class _FixDictReader(csv.DictReader):
    ('TextIOWrapper automatically closes, when the underlying buffer runs out.\n'
     "Because of this, when the DictReader calls next on it's underlying reader object,\n"
     "it's buffer will be closed, when the file is done being read.\n"
     "to mitigate this, we catch the exception and raise StopIteration")

    def __next__(self):
        try:
            return super().__next__()
        except ValueError as error:
            if str(error) != 'I/O operation on closed file.':
                raise
            raise StopIteration

def csv_to_pricebooks(csvfile, currency="USD"):
    reader = _FixDictReader(csvfile)

    pricebook = 'default' if currency == "CAD" else f"{currency.lower()}-prices"

    default_price_book = {
        'head': {
            'pricebook': pricebook,
            'catalog': f'storefront-catalog-en',
            'currency': currency
        },
        'items': [],
    }

    for item in reader:
        product_id = item['ProductSKU']
        default_price_book['items'].append({
            'product_id': product_id,
            'value': float(item['Price'])
        })

    return default_price_book
