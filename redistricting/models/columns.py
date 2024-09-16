
from typing import (
    Any,
    Iterable
)

from ..utils import tr


class ConstStr(str):
    _index_: int
    comment: str

    def __new__(cls, value, index, comment):
        inst = super().__new__(cls, value)
        inst._index_ = index
        inst.comment = comment
        return inst

    def __int__(self):
        return self._index_


class ConstantsMeta(type):
    """Simplified Enum type class where members are of the type of their value, not an instance of the Enum subclass"""
    _member_names: dict[str, ConstStr]

    def __new__(cls, name, bases, classdict: dict[str, Any]):
        ignore = classdict.get('_ignore', [])

        member_names = {}
        for f, v in classdict.items():
            if f.startswith("_") or f in ignore or isinstance(v, type):
                continue

            if hasattr(v, '__qualname__') and v.__qualname__.startswith(f'{name}.'):
                continue

            if f in member_names:
                raise TypeError(f'{f!r} already defined as {member_names[f]!r}')

            if isinstance(v, tuple):
                v, comment = v
            else:
                comment = None

            if isinstance(v, str) and not isinstance(v, ConstStr):
                classdict[f] = ConstStr(v, len(member_names), comment)
                member_names[f] = classdict[f]
            else:
                member_names[f] = v

        classdict['_member_names'] = member_names
        return super().__new__(cls, name, bases, classdict)

    def __iter__(cls):
        for v in cls._member_names.values():
            yield v

    def items(cls):
        return cls._member_names.items()

    def keys(cls):
        return cls._member_names.keys()

    def values(cls):
        return cls._member_names.values()


class DistrictColumns(metaclass=ConstantsMeta):
    DISTRICT = "district", tr("District")
    NAME = "name", tr("Name")
    MEMBERS = "members", tr("Members")
    POPULATION = "population", tr("Population")
    DEVIATION = "deviation", tr("Deviation")
    PCT_DEVIATION = "pct_deviation", tr("%Deviation")


class MetricsColumns(metaclass=ConstantsMeta):
    POLSBYPOPPER = "polsbypopper", tr("Polsby-Popper")
    REOCK = "reock", tr("Reock")
    CONVEXHULL = "convexhull", tr("Convex Hull")
    PIECES = "pieces", tr("Pieces")

    @classmethod
    def CompactnessScores(cls) -> Iterable[ConstStr]:
        return MetricsColumns.POLSBYPOPPER, MetricsColumns.REOCK, MetricsColumns.CONVEXHULL
