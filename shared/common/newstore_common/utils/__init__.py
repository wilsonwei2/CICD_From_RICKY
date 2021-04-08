from newstore_common.json.decimal_encoder import DecimalToStringEncoder
from collections.abc import Iterator


def compare_ordinal(value_1: str, value_2: str) -> bool:
    return value_1.lower().strip() == value_2.lower().strip()


def flatten(it: list):
    for x in it:
        # allow iterator for yields
        if isinstance(x, Iterator) or isinstance(x, list):
            yield from flatten(x)
        else:
            yield x


# Deprecated
# from newstore_common.caching.cached_property import CachedProperty
class CachedProperty(object):
    def __init__(self, func, name=None):
        self.func = func
        self.name = name if name is not None else func.__name__
        self.__doc__ = func.__doc__

    def __get__(self, instance, class_):
        if instance is None:
            return self
        ret = self.func(instance)
        setattr(instance, self.name, ret)  # works since __get__ won't be called if the attr is set
        return ret


# Deprecated
# from newstore_common.json.decimal_encoder import DecimalToStringEncoder
class DecimalEncoder(DecimalToStringEncoder):
    pass