
from typing import Any


class ConstStr(str):
    def __new__(cls, value, index):
        inst = super().__new__(cls, value)
        inst.index = index
        return inst

    def __int__(self):
        return self.index


class ConstantsMeta(type):
    """Simplified Enum type class where members are of the type of their value, not an instance of the Enum subclass"""
    def __new__(metacls, cls, bases, classdict: dict[str, Any]):
        ignore = classdict.get('_ignore', [])

        member_names = {}
        for f, v in classdict.items():
            if f.startswith("_") or f in ignore or isinstance(v, type):
                continue

            if hasattr(v, '__qualname__') and v.__qualname__.startswith(f'{cls}.'):
                continue

            if f in member_names:
                raise TypeError('%r already defined as %r' % (f, member_names[f]))

            if isinstance(v, str) and not isinstance(v, ConstStr):
                classdict[f] = ConstStr(v, len(member_names))
                member_names[f] = classdict[f]
            else:
                member_names[f] = v

        classdict['_member_names'] = member_names
        return super().__new__(metacls, cls, bases, classdict)

    def __iter__(cls):
        for v in cls._member_names.values():
            yield v

    def items(cls):
        return cls._member_names.items()

    def keys(cls):
        return cls._member_names.keys()

    def values(cls):
        return cls._member_names.values()


class Constants(metaclass=ConstantsMeta):
    _member_names: dict[str, Any]


class DistrictColumns(Constants):
    DISTRICT = "district"
    NAME = "name"
    MEMBERS = "members"
    POPULATION = "population"
    DEVIATION = "deviation"
    PCT_DEVIATION = "pct_deviation"


class StatsColumns(Constants):
    POLSBYPOPPER = "polsbypopper"
    REOCK = "reock"
    CONVEXHULL = "convexhull"
    PIECES = "pieces"

    @classmethod
    def CompactnessScores(cls):
        return StatsColumns.POLSBYPOPPER, StatsColumns.REOCK, StatsColumns.CONVEXHULL
