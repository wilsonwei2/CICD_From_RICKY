import os
import csv


class Utils():
    _countries = {}

    @staticmethod
    def get_countries_map():
        if not Utils._countries:
            filename = os.path.join(os.path.dirname(__file__), 'iso_country_codes.csv')
            with open(filename) as country_file:
                file = csv.DictReader(country_file, delimiter=',')
                for line in file:
                    Utils._countries[line['Alpha-2 code']] = Utils._format_country_name(line['English short name lower case'])
        return Utils._countries

    @staticmethod
    def _format_country_name(country_name):
        func = lambda s: s[:1].lower() + s[1:] if s else ''
        return f'_{func(country_name).replace(" ", "")}'

    # Gets the information about the discounts of an item
    @staticmethod
    def get_discount_info(item):
        has_item_discount = float(item['item_discounts']) > 0
        has_order_discount = float(item['order_discounts']) > 0
        has_discount = has_item_discount or has_order_discount
        total_discount = abs(
            float(item['item_discounts']) + float(item['order_discounts']))

        return has_item_discount, has_order_discount, has_discount, total_discount
