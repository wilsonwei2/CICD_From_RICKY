import logging

from lambda_utils.newstore_api.jobs_manager import JobsManager

logger = logging.getLogger()

ATTR_MAP = {
    'multi_value': {'tag': 'tags'},
    'type_cast': {'is_main': bool, 'position': int, 'weight': int},
    'value_cast': {'true': True, '1': True, 1: True, 'false': False, '0': False, 0: False}
}


class FailSafeDict(dict):
    @property
    def import_job(self):
        return self._import_job

    @import_job.setter
    def import_job(self, import_job):
        self._import_job = import_job

    def __missing__(self, key):
        # KeyError Custom Handling
        logger.fatal('Missing key %s ' % key)
        self.jobs_manager = JobsManager()
        if self._import_job:
            self.jobs_manager.fail_job(self._import_job, 'Missing Key %s' % key)
        exit(0)


class ResultDict(dict):
    def __init__(self, **kwargs):
        """
        Makes sure to call self.__setitem__()
        """
        for k, v in kwargs.iteritems():
            self[k] = v

    def __setitem__(self, key, value):
        """
        We only want non-empty values.
        """
        if value or value == 0:
            super(ResultDict, self).__setitem__(key, value)

    def set_extended_attributes(self, lookup, extended_attributes):
        """
        Fills extended attributes if any.

        :param dict lookup: current line that we're working with
        :param list extended_attributes: list of extended attribute names
        """
        self['extended_attributes'] = [{'name': attr, 'value': lookup[attr]} for attr in extended_attributes]

    def set_external_identifiers(self, lookup, external_identifiers):
        """
        Fills external identifiers if any.

        :param dict lookup: current line that we're working with
        :param list external_identifiers: list of external identifiers
        """
        self['external_identifiers'] = [
            {'type': attr.lower(), 'value': lookup[attr]} for attr in external_identifiers if attr in lookup]

    @classmethod
    def _get_image_attributes(cls, key, value, add_internal_attributes, is_legacy_format):
        """
        This is a private method which is called by set_delimited_attributes to set some image specific stuff.

        :param string key: Current lookup key (see caller for details)
        :param string value: Current lookup value (see caller for details)
        :param bool add_internal_attributes: Whether to add internal attributes to attr
        :param bool is_legacy_format: Whether we want to return legacy stuff
        """
        attrs = {}

        if add_internal_attributes:
            attrs['internal_dimension_height'] = 200
            attrs['internal_dimension_width'] = 200
            attrs['internal_dominant_color'] = '#FFFFFF'

        if is_legacy_format:
            attrs['url'] = value

            if add_internal_attributes:
                attrs['title'] = key  # respect behaviour of original set_images() function

        return attrs

    @classmethod
    def _get_category_attributes(cls, key, value, add_internal_attributes, is_legacy_format):
        """
        This is a private method which is called by set_delimited_attributes to set some category specific stuff.

        :param string key: Current lookup key (see caller for details)
        :param string value: Current lookup value (see caller for details)
        :param bool add_internal_attributes: Whether to add internal attributes to attr
        :param bool is_legacy_format: Whether we want to return legacy stuff
        """
        attrs = {}

        if is_legacy_format:
            attrs['path'] = value

        return attrs

    def set_delimited_attributes(self, lookup, kind, key, root, add_internal_attributes=True, multi_attr_map=None,
                                 cast_attr_map=None, count_delim='_', attr_delim='::'):
        """
        Finds all values of the current line with the column name separated by attr_delim argument and puts them
        to item. Supports 2 formats which can be mixed together if needed:

        1. ATTR_N - old simple format where only some basic stuff is supported, see self.set_KIND_attributes()
        2. ATTR_N::ATTR[_N] - new format with support for extended attributes, e.g. IMAGE_1::URL, IMAGE_1::TAG_1 etc

        :param dict lookup: map of keys to values of the current CSV line
        :param string kind: attribute kind, e.g. image, category etc
        :param string key: key that is used to find attr related columns
        :param string root: key name that is used to put all images into the item
        :param bool add_internal_attributes: Whether to add internal attributes to attr
        :param dict multi_attr_map: mapping of attrs with multiple values from CSV to item
        :param dict cast_attr_map: mapping of attr name to type to cast to
        :param string count_delim: delimiter that is used to find current attribute count
        :param string attr_delim: delimiter that is used to find extended attributes
        """
        items, result = {}, []
        kind_method = getattr(self, '_get_%s_attributes' % kind, lambda *args, **kwargs: {})

        if multi_attr_map is None:
            multi_attr_map = ATTR_MAP['multi_value']

        if cast_attr_map is None:
            cast_attr_map = ATTR_MAP['type_cast']

        # generates all attribute data with order hints in one go
        for lookup_key in lookup:
            if not '%s%s' % (key, count_delim) in lookup_key:
                continue

            lookup_value = lookup[lookup_key].strip()

            if not lookup_value:
                continue

            parts = lookup_key.split(attr_delim)
            _, count = parts[0].split(count_delim)

            if count not in items:
                items[count] = kind_method(lookup_key, lookup_value, add_internal_attributes, False)

            if len(parts) == 1:  # old format without extended attributes support, i.e. ATTR_1, ATTR_2
                items[count] = kind_method(lookup_key, lookup_value, add_internal_attributes, True)

                if count == 1:
                    items[count]['is_main'] = True
            else:
                attr = parts[1].lower()
                attr_parts = attr.split(count_delim)

                if len(attr_parts) == 2 and attr_parts[1].isdigit():  # attr with multiple values, i.e. ATTR_1::NAME
                    attr, attr_count = attr_parts

                    if attr in multi_attr_map:
                        if not multi_attr_map[attr] in items[count]:
                            items[count][multi_attr_map[attr]] = {}

                        items[count][multi_attr_map[attr]][attr_count] = cast_attr_map.get(attr, str)(lookup_value)
                else:
                    items[count][attr] = cast_attr_map.get(attr, str)(lookup_value)

        # inserts data maintaining same order as in CSV using order hints from above
        for ii in sorted(items):
            for multi_attr in multi_attr_map.values():
                if multi_attr in items[ii]:
                    items[ii][multi_attr] = [items[ii][multi_attr][ai] for ai in sorted(items[ii][multi_attr])]

            result.append(items[ii])

        self[root] = result
