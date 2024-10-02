# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - District classes

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022-2024 by Cryptodira
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
from itertools import repeat
from typing import (
    Annotated,
    Any,
    Iterable,
    Literal,
    Optional,
    Union,
    overload
)

from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)

from ..utils import tr
from .base import (
    SortedKeyedList,
    in_range,
    not_empty,
    rds_property
)
from .columns import (
    DistrictColumns,
    MetricsColumns
)


class RdsDistrict(QObject):
    BASE_COLUMNS = list(DistrictColumns)
    STATS_COLUMNS = list(MetricsColumns)
    WRITABLE_ATTRIBUTES = (DistrictColumns.NAME, int(DistrictColumns.NAME),
                           DistrictColumns.MEMBERS, int(DistrictColumns.MEMBERS))

    nameChanged = pyqtSignal()
    membersChanged = pyqtSignal()
    descriptionChanged = pyqtSignal()

    district: int
    name: Annotated[str, not_empty] = rds_property(notify=nameChanged)
    members: Annotated[int, in_range(0, 9999)] = rds_property(notify=membersChanged)
    population: int = 0
    deviation: int = 0
    pct_deviation: float = 0.0
    description: str = rds_property(private=True, notify=descriptionChanged)
    fid: int = -1

    def __init__(self, district: int, name: Optional[str] = None, members: Optional[int] = 1, description: str = '', fid=-1, **kwargs):
        super().__init__()
        self.fid = fid
        self._data = {
            DistrictColumns.DISTRICT: district,
            DistrictColumns.NAME: name or str(district),
            DistrictColumns.MEMBERS: members,
            DistrictColumns.POPULATION: 0,
            DistrictColumns.DEVIATION: 0,
            DistrictColumns.PCT_DEVIATION: 0.0,
        }
        self._description = description
        self._data.update(zip(RdsDistrict.STATS_COLUMNS, repeat(None)))

        self.update(kwargs)

    def __key__(self):
        return str(self.district).rjust(4, "0")

    def clone(self):
        return self.__class__(fid=self.fid, description=self.description, **self._data)

    def __contains__(self, index: str):
        return index in self._data

    @overload
    def __getitem__(self, index: Union[str, int]) -> Any:
        ...

    @overload
    def __getitem__(self, index: slice) -> dict[str, Any]:
        ...

    def __getitem__(self, key: Union[int, str, slice]):
        if isinstance(key, str) and key in self._data:
            value = self._data[key]
        elif isinstance(key, int) and 0 <= key < len(self._data):
            value = list(self._data.values())[key]
        elif isinstance(key, slice):
            keys = list(self._data.keys())[key]
            value = {k: self._data[k] for k in keys}
        else:
            raise IndexError(f"{key} not found in district")

        return value

    def __setitem__(self, key: Union[int, str], value: Any):
        if key not in RdsDistrict.WRITABLE_ATTRIBUTES:
            raise IndexError(f"Field '{key}' is readonly")

        if isinstance(key, int):
            if 0 <= key < len(self._data):
                key = list(self._data.keys())[key]
            else:
                raise IndexError(f"no item at index {key}")

        self._data[key] = value

    def __eq__(self, __value: "RdsDistrict"):
        if __value is None:
            return False

        if not isinstance(__value, RdsDistrict):
            return NotImplemented

        return self._data == __value._data

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]

        return super().__getattr__(name)

    @rds_property
    def district(self):
        return self._data[DistrictColumns.DISTRICT]

    @name.getter
    def name(self):
        return self._data[DistrictColumns.NAME]

    @name.setter
    def name(self, value: str):
        self._data[DistrictColumns.NAME] = value

    @members.getter
    def members(self):
        return self._data[DistrictColumns.MEMBERS]

    @members.setter
    def members(self, value: int):
        self._data[DistrictColumns.MEMBERS] = value

    @rds_property
    def population(self):
        return self._data[DistrictColumns.POPULATION]

    @population.setter
    def population(self, value: int):
        self._data[DistrictColumns.POPULATION] = value

    @rds_property
    def deviation(self):
        return self._data[DistrictColumns.DEVIATION]

    @deviation.setter
    def deviation(self, value: int):
        self._data[DistrictColumns.DEVIATION] = value

    @rds_property
    def pct_deviation(self):
        return self._data[DistrictColumns.PCT_DEVIATION]

    @pct_deviation.setter
    def pct_deviation(self, value: float):
        self._data[DistrictColumns.PCT_DEVIATION] = value

    @property
    def columns(self):
        return list(self._data.keys())

    def extend(self, columns: Iterable[str]):
        data = self._data
        addcols = [c for c in columns if c not in RdsDistrict.BASE_COLUMNS and c not in RdsDistrict.STATS_COLUMNS]
        self._data = dict.fromkeys(RdsDistrict.BASE_COLUMNS + addcols + RdsDistrict.STATS_COLUMNS)
        self._data.update(data)

    @overload
    def update(self, data: "RdsDistrict"):
        ...

    @overload
    def update(self, data: dict[str, Any]):
        ...

    def update(self, data: Union["RdsDistrict", dict[str, Any]]):
        if isinstance(data, RdsDistrict):
            self.fid = data.fid
            data = data[:]

        newkeys = [k for k in data.keys() if k not in RdsDistrict.BASE_COLUMNS + RdsDistrict.STATS_COLUMNS]
        self._data = dict.fromkeys(RdsDistrict.BASE_COLUMNS + newkeys + RdsDistrict.STATS_COLUMNS) | self._data | data


class RdsUnassigned(RdsDistrict):
    district: Literal[0] = rds_property(fget=RdsDistrict.district.fget)
    name: str = rds_property(fget=RdsDistrict.name.fget)
    members: Optional[int] = None
    deviation: Optional[int] = None
    pct_deviation: Optional[float] = None

    def __init__(self, *, fid=-1, **kwargs):
        if DistrictColumns.DISTRICT in kwargs:
            del kwargs[DistrictColumns.DISTRICT]
        if DistrictColumns.NAME in kwargs:
            del kwargs[DistrictColumns.NAME]
        kwargs[DistrictColumns.MEMBERS] = None
        kwargs[DistrictColumns.DEVIATION] = None
        kwargs[DistrictColumns.PCT_DEVIATION] = None

        super().__init__(0, tr("Unassigned"), fid=fid, **kwargs)

    def __setitem__(self, key: Union[str, int, slice], value: Any):
        raise IndexError(tr("'{key}' field is readonly for Unassigned goegraphies").format(key=key))

    def update(self, data: Union["RdsDistrict", dict[str, Any]]):
        super().update(data)

        self._data[DistrictColumns.NAME] = tr("Unassigned")
        self._data[DistrictColumns.MEMBERS] = None
        self._data[DistrictColumns.DEVIATION] = None
        self._data[DistrictColumns.PCT_DEVIATION] = None

        self._data.update(zip(RdsDistrict.STATS_COLUMNS, repeat(None)))


class DistrictList(SortedKeyedList[RdsDistrict]):  # pylint: disable=abstract-method
    def clear(self):
        addUnassigned = '0000' in self._keys

        super().clear()

        if addUnassigned:
            self.append(RdsUnassigned())

    def __contains__(self, item: Union[int, str, RdsDistrict]):
        if isinstance(item, int):
            item = str(item)

        if isinstance(item, str):
            return item in self._items

        return item in self._items.values()
