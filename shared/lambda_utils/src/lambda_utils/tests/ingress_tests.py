import unittest
import csv
import os
import sys
from ..ingress import reader

class IngressTestCase(unittest.TestCase):

    def test_import_with_no_traits(self):
        """Parse import with no pricebook traits"""
        file_name = os.path.join(os.path.dirname(__file__), '../../../', 'test_data', 'no_traits.txt')

        params = read_file(file_name)
        traits = parse_traits(params)
        self.assertEqual([], traits, 'Traits are not assigned to any pricebook')

    def test_import_with_traits_for_one_pricebook(self):
        """Only default pricebook has traits assigned"""
        file_name = os.path.join(os.path.dirname(__file__), '../../../', 'test_data', 'traits_in_one_pb.txt')

        params = read_file(file_name)
        traits = parse_traits(params)
        self.assertEqual(['default', 'list_prices'], traits, 'Default pricebook has traits assigned')

    def test_import_with_traits_for_multiple_pricebooks(self):
        """Multiple pricebooks have traits assigned"""
        file_name = os.path.join(os.path.dirname(__file__), '../../../', 'test_data', 'traits_in_multi_pricebooks.txt')

        params = read_file(file_name)
        traits = parse_traits(params)
        self.assertEqual(['default', 'list_prices', 'overwrite'], traits, 'Multiple traits for 2 pricebooks')

    def test_import_with_store_mappings(self):
        """Store mappings should be in the header and mapped"""
        file_name = os.path.join(os.path.dirname(__file__), '../../../', 'test_data', 'store_mappings.txt')

        params = read_file(file_name)
        head = parse_header(params)
        self.assertEqual(3, len(head['store_mapping']), 'Multiple traits for 2 pricebooks')


def read_file(filename):
    params = {
        'data' : ''
    }

    with open(filename, 'rb') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter = ',', quotechar = '\'')
        for row in csv_reader:
            params['data'] = params['data'] + ','.join(row) + '\n'

    return params

def parse_traits(params):
    csvreader = reader.CSVReader(params['data'])
    head, pricebooks = csvreader.head, {}
    traits = []
    for lookup in csvreader.content:
        pbname = lookup.pop('PRICEBOOK', 'default')  # if there's no pricebook info, give it default name
        if pbname not in pricebooks:
            pb_traits = csvreader.parse_head_with_traits(pbname)
            pricebooks[pbname] = True
            if pb_traits:
                traits.extend(pb_traits)

    return traits

def parse_header(params):
    csvreader = reader.CSVReader(params['data'])
    return csvreader.head
