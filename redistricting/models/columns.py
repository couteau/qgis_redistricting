
from enum import IntEnum
from typing import (
    Any,
    Iterable
)

from qgis.PyQt.QtGui import QColor

from ..utils import tr


class FieldCategory(IntEnum):
    Population = 1
    Geography = 2
    Demographic = 3
    Metrics = 4
    User = 5


FieldColors = {
    FieldCategory.Population: QColor(0x566f9fff),
    FieldCategory.Geography: QColor(0xcfeb9fff),
    FieldCategory.Demographic: QColor(0x5c98a9ff),
    FieldCategory.Metrics: QColor(0x83df86ff),
    FieldCategory.User: QColor(0x9189d7ff),
    FieldCategory.User + 1: QColor(0xab89d7ff),
    FieldCategory.User + 2: QColor(0xcc94e3ff),
    FieldCategory.User + 3: QColor(0xdda6d8ff),
    FieldCategory.User + 4: QColor(0xf594c6ff)
}


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
    """Simplified Enum type class where members are strings, not instances of the Enum"""
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

            if isinstance(v, str):
                if not isinstance(v, ConstStr):
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
