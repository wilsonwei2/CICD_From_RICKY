import csv
import datetime
import logging
from cStringIO import StringIO
from structures import FailSafeDict, ATTR_MAP

logger = logging.getLogger()

class ContentReadError(Exception):
     def __init__(self, value):
         self.value = value
     def __str__(self):
         return repr(self.value)
class ContentReader(csv.DictReader):
    def next(self):
        values = csv.DictReader.next(self)
        decoded_values = {}
        for k, v in values.iteritems():
            try:
                decoded_values[k] = v.decode('string_escape')
            except Exception:
                logger.error('Failed to decode \'%s\': \'%s\'', k, v)

        if len(values) != len(decoded_values):
            raise ContentReadError('Failed to decode \'{}\''.format(values))           
        return FailSafeDict(decoded_values)

class CSVReader(object):
    path_map = {
        '*': '$.{}',
        'extended_attributes': '$.extended_attributes[?(@.name == \'{}\')].value',
        'external_identifiers': '$.external_identifiers[?(@.type == \'{}\')].value',
    }

    def __init__(self, csv_content, with_extra_attributes=False, init_head_call=None, *args, **kwargs):
        """
        :param string csv_content: Contents of CSV file as a string
        :param bool with_extra_attributes: Whether to populate a head with extra attributes or not
        :param callable init_head_call: A callable to use for head initiation
        """
        self.file_object = StringIO(csv_content)
        self.csv_args, self.csv_kwargs = args, kwargs
        self.head, self.extended_attributes, self.external_identifiers, self.is_full_import, extra_attributes, self.traits, self.release_allocations = (
            init_head_call or self.init_head)()

        if with_extra_attributes:
            for attr_type, attrs in extra_attributes.items():
                self.with_extra_attributes(attr_type, attrs)

        self.content = ContentReader(self.file_object, *args, **kwargs)

    @staticmethod
    def get_default_head():
        """
        Returns default header dictionary.
        """
        return {
            'catalog': 'storefront-catalog-en', # TODO remove this entry as it is deprecated
            'shop': 'storefront-catalog-en',
            'locale': 'en-US'
        }

    @classmethod
    def get_typed_value(cls, value, column=None):
        """
        Tries to get the value in it's correct type, if column is passed, tries to typecast using cast type mapping.

        :param any value: Value
        :param str column: Column name
        """
        if column is not None and column in ATTR_MAP['type_cast']:
            return ATTR_MAP['type_cast'][column](value)

        return ATTR_MAP['value_cast'].get(value.lower() if hasattr(value, 'lower') else value, value)

    @classmethod
    def get_datetime_from_date(cls, value, fmt='%Y-%m-%d'):
        """
        Converts string date to string datetime.

        :param string value: Value to convert
        :param string fmt: Date format for input/output
        """
        return datetime.datetime.strptime(value, fmt).strftime('{}T%H:%M:%S.000Z'.format(fmt))

    def with_extra_attributes(self, attr_type, attributes):
        """
        Populates head with extra attributes, e.g. filterable, searchable etc.

        :param string attr_type: Extra attribute type, e.g. filterable, searchable etc.
        :param dict attributes: Attributes to populate head with.
        """
        extra_attibutes = []

        for attr in attributes.values():
            if 'path' not in attr:
                if attr['name'] in self.external_identifiers:
                    path_type = 'external_identifiers'
                elif attr['name'] in self.extended_attributes:
                    path_type = 'extended_attributes'
                else:
                    path_type = '*'

                attr['path'] = self.path_map[path_type].format(attr['name'])

            extra_attibutes.append(attr)

        if extra_attibutes:
            self.head[attr_type] = extra_attibutes

    def init_head(self):
        """
        Parses header of CSV file and sets a few helper variables which contain the gathered header data.
        """
        extended_attributes, external_identifiers = [], []
        extra_attributes = {'searchable_attributes': {}, 'filterable_attributes': {}}
        head = self.get_default_head()

        reader = csv.reader(self.file_object, *self.csv_args, **self.csv_kwargs)
        csv_head = zip(*(next(reader) for _ in range(2)))  # we assume that head is constructed from first 2 lines

        for column, value in csv_head:
            if column and value:  # we don't need empty columns and values
                column = column.lower()
                value = self.get_typed_value(value)
                if column.startswith('extended_attribute_'):
                    extended_attributes.append(value)
                elif column.startswith('external_identifier_'):
                    external_identifiers.append(value)
                elif column.startswith('searchable_attribute_') or column.startswith('filterable_attribute_'):
                    attr_type, attr_subtype = column.split('::')
                    attr_type_name, attr_type_position = attr_type.rsplit('_', 1)
                    attr_type_name += 's'

                    if attr_type_position not in extra_attributes[attr_type_name]:
                        extra_attributes[attr_type_name][attr_type_position] = {}

                    value = self.get_typed_value(value, column=attr_subtype)
                    extra_attributes[attr_type_name][attr_type_position][attr_subtype] = value
                else:
                    head[column] = value

        is_full_import = head.pop('is_full', False)  # replace all data with new one
        release_allocations = head.pop('release_allocations', False)  # release allocations
        # get traits if there are any
        traits = head.pop('traits', None)
        # are there any store mappings in the head
        store_mappings = self.get_store_mappings(head)
        if store_mappings:
            head['store_mapping'] = store_mappings
        return head, extended_attributes, external_identifiers, is_full_import, extra_attributes, traits, release_allocations

    def parse_head_with_traits(self, name):
        """ Parses a CSV imports traits if they are listed in the header
        The header is in form:

            SHOP,CURRENCY,IS_FULL,TRAITS
            storefront-catalog-en,USD,True,"default:default,list_prices|gift-card-5:overwrite"

        The parsed header for the default pricebook will be:
            "head": {
                "locale": "en-US",
                "currency": "USD",
                "shop": "storefront-catalog-en",
                "traits": [
                    "default",
                    "list_prices"
                ],
                "pricebook": "default"
            }
        """
        if not self.traits:
            return None

        # meaning that traits for only one pricebook have been specified
        if self.traits.find('|') == -1:
            return self.parse_traits(self.traits, name)

        all_traits = self.traits.split('|')

        traits = [
            trait for trait in all_traits if self.has_traits(trait, name)]

        if not traits:
            return None

        return self.parse_traits(traits[0], name)

    def parse_traits(self, trait, name):
        # meaning that traits for only one pricebook have been specified
        if not self.has_traits(trait, name):
            return None

        specific_traits = trait[trait.index(':') + 1:]
        return specific_traits.split(',')

    def has_traits(self, trait, name):
        return trait.find(name + ':') != -1

    def get_store_mapping(self, mapping_string):
        mapping_arr = mapping_string.split(':')
        return dict(store_id=mapping_arr[0], fulfillment_node_id=mapping_arr[1])

    def get_store_mappings(self, head):
        """ Parses the store mapping if any, from the header and creates a mappings
        array out of them:
        Intitally :
            store_mapping : "store_id_1:fulfillment_node_id_1, store_id_2:fulfillment_node_id_2"
        Converted:
            store_mapping : [{
                "store_id" : "store_id_1",
                "fulfillment_node_id" : "fulfillment_node_id_1"
            },
            {
                "store_id" : "store_id_2",
                "fulfillment_node_id" : "fulfillment_node_id_2"
            }]
        """

        if 'store_mapping' not in head:
            return None
        store_mapping_strings = head['store_mapping'].split(',')
        return [self.get_store_mapping(x) for x in store_mapping_strings]

