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

def csv_to_pricebooks(csvfile, currency, catalog, is_sale):
    reader = _FixDictReader(csvfile)

    pricebook_name = 'default' if currency == 'CAD' else f'{currency.lower()}-prices'

    price_book = {
        'head': {
            'pricebook': pricebook_name,
            'catalog': catalog,
            'currency': currency
        },
        'items': [],
    }

    for line_no, item in enumerate(reader, start=1):
        try:
            product_id = item['ProductSKU']
            price_value = float(item['Price'])

            # skip 0 prices for sale prices
            if price_value == 0 and is_sale:
                continue

            price_book['items'].append({
                'product_id': product_id,
                'value': price_value
            })
        except Exception:
            LOGGER.error(f'error proceessing line {line_no}')
            raise

    return price_book
