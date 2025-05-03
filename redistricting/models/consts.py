# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - base str enum class and enums

        begin                : 2024-09-15
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Cryptodira
        email                : stuart@cryptodira.org

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 *   This program is distributed in the hope that it will be useful, but   *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the          *
 *   GNU General Public License for more details. You should have          *
 *   received a copy of the GNU General Public License along with this     *
 *   program. If not, see <http://www.gnu.org/licenses/>.                  *
 *                                                                         *
 ***************************************************************************/
"""
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
    _index: int
    comment: str

    def __new__(cls, value, comment=None, index=None):
        inst = super().__new__(cls, value)
        inst.comment = comment
        inst._index = index
        return inst

    def __int__(self):
        return self._index


class ConstantsMeta(type):
    """Simplified Enum type class where members are strings, not instances of the Enum"""
    _members: dict[str, ConstStr]

    def __new__(cls, name, bases, classdict: dict[str, Any]):
        ignore = classdict.get('_ignore', [])
        cls._nextindex_ = 0

        members = {}
        for c in bases:
            # TODO: check for conflicts if multiple bases are ConstantsMeta instances
            if isinstance(c, ConstantsMeta):
                members.update(c._members)

        for f, v in classdict.items():
            if f.startswith("_") or f in ignore or isinstance(v, type):
                continue

            if hasattr(v, '__qualname__') and v.__qualname__.startswith(f'{name}.'):
                continue

            if f in members:
                raise TypeError(f'{f!r} already defined as {members[f]!r}')

            if isinstance(v, tuple):
                v, comment = v
            else:
                comment = None

            if isinstance(v, str):
                if not isinstance(v, ConstStr):
                    classdict[f] = ConstStr(v, comment, cls._nextindex_)
                    members[f] = classdict[f]
                else:
                    if v._index is None:
                        v._index = cls._nextindex_
                    else:
                        cls._nextindex_ = v._index

                    members[f] = v

                cls._nextindex_ += 1

        classdict['_members'] = members
        return super().__new__(cls, name, bases, classdict)

    def __iter__(cls):
        for v in cls._members.values():
            yield v

    def items(cls):
        return cls._members.items()

    def keys(cls):
        return cls._members.keys()

    def values(cls):
        return cls._members.values()


class DistrictColumns(metaclass=ConstantsMeta):
    DISTRICT = ConstStr("district", tr("District"))
    NAME = ConstStr("name", tr("Name"))
    MEMBERS = ConstStr("members", tr("Members"))
    POPULATION = ConstStr("population", tr("Population"))
    DEVIATION = ConstStr("deviation", tr("Deviation"))
    PCT_DEVIATION = ConstStr("pct_deviation", tr("%Deviation"))


class MetricsColumns(metaclass=ConstantsMeta):
    POLSBYPOPPER = ConstStr("polsbypopper", tr("Polsby-Popper"))
    REOCK = ConstStr("reock", tr("Reock"))
    CONVEXHULL = ConstStr("convexhull", tr("Convex Hull"))
    PIECES = ConstStr("pieces", tr("Pieces"))

    @classmethod
    def CompactnessScores(cls) -> Iterable[ConstStr]:
        return MetricsColumns.POLSBYPOPPER, MetricsColumns.REOCK, MetricsColumns.CONVEXHULL


class DeviationType(IntEnum):
    OverUnder = 0
    TopToBottom = 1
