"""
Transformer.py

Transformer for converting the CSV data to price import job payload for import jobs.

@author Aditya Kasturi akasturi@newstore.com
"""
import csv
import logging
import sqlite3

from datetime import datetime

CONNECTION = sqlite3.connect(':memory:')
CONNECTION.row_factory = sqlite3.Row
CURSOR = CONNECTION.cursor()

LOGGER = logging.getLogger()

CURSOR.execute('''CREATE TABLE prices(
    netsuite_id text,
    price numeric,
    price_level text,
    name text,
    internal_id numeric
);''')
CONNECTION.commit()

QUERY = \
'''SELECT *
FROM   prices
ORDER  BY netsuite_id,
          price
'''

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

def csv_to_pricebooks(csvfile):
    reader = _FixDictReader(csvfile)

    for item in reader:
        CURSOR.execute('INSERT INTO prices VALUES (?,?,?,?,?)', tuple(item.values()))

    CONNECTION.commit()

    default_price_book = {
        'head': {
            'pricebook': 'default',
            'catalog': 'storefront-catalog-en',
            'currency': 'USD'
        },
        'items': [],
    }

    for item in CURSOR.execute(QUERY):
        product_id = str(item['netsuite_id'])
        default_price_book['items'].append({
            'product_id': product_id,
            'value': float(item['price'])
        })

    LOGGER.info(default_price_book)

    return default_price_book
