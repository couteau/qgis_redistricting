# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - District classes

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
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
from typing import (
    Any,
    Iterable,
    Literal,
    Union,
    overload
)

from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)

from ..utils import tr
from .columns import (
    DistrictColumns,
    StatsColumns
)


class District(QObject):
    BASE_COLUMNS = [
        DistrictColumns.DISTRICT,
        DistrictColumns.NAME,
        DistrictColumns.MEMBERS,
        DistrictColumns.POPULATION,
        DistrictColumns.DEVIATION,
        DistrictColumns.PCT_DEVIATION,
    ]
    STATS_COLUMNS = [
        StatsColumns.POLSBYPOPPER,
        StatsColumns.REOCK,
        StatsColumns.CONVEXHULL,
        StatsColumns.PIECES
    ]
    WRITABLE_ATTRIBUTES = (DistrictColumns.NAME, int(DistrictColumns.NAME),
                           DistrictColumns.MEMBERS, int(DistrictColumns.MEMBERS))

    nameChanged = pyqtSignal()
    membersChanged = pyqtSignal()
    descriptionChanged = pyqtSignal()

    district: int
    name: str
    members: int
    population: int
    deviation: int
    pct_deviation: float

    def __init__(self, district: int, fid: int = -1, *, description="", **kwargs):
        super().__init__()
        self._district = district
        self._fid = fid
        self._description = description
        self._data = {
            DistrictColumns.DISTRICT: self._district,
            DistrictColumns.NAME: str(district),
            DistrictColumns.MEMBERS: 1,
            DistrictColumns.POPULATION: 0,
            DistrictColumns.DEVIATION: 0,
            DistrictColumns.PCT_DEVIATION: 0.0,
        }
        self.update(kwargs)

    def __repr__(self):
        return f"District({self._district} - '{self.name}' ({self.population}))"

    def clone(self):
        return self.__class__(fid=self._fid, description=self._description, **self._data)

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
        if key not in District.WRITABLE_ATTRIBUTES:
            raise IndexError(f"Field '{key}' is readonly")

        if isinstance(key, int):
            if 0 <= key < len(self._data):
                key = list(self._data.keys())[key]
            else:
                raise IndexError(f"no item at index {key}")

        self._data[key] = value
        if key == DistrictColumns.NAME:
            self.nameChanged.emit()
        elif key == DistrictColumns.MEMBERS:
            self.membersChanged.emit()

    def __eq__(self, __value: "District"):
        return self._district == __value._district and self._data == __value._data

    @property
    def district(self):
        return self._district

    @property
    def fid(self):
        return self._fid

    @property
    def name(self):
        return self._data[DistrictColumns.NAME]

    @name.setter
    def name(self, value: str):
        assert isinstance(value, str) and value != ""
        try:
            self[DistrictColumns.NAME] = value
        except IndexError as e:
            raise AttributeError(e) from e

    @property
    def members(self):
        return self._data[DistrictColumns.MEMBERS]

    @members.setter
    def members(self, value: int):
        assert isinstance(value, int) and value > 0
        try:
            self[DistrictColumns.MEMBERS] = value
        except IndexError as e:
            raise AttributeError(e) from e

    @property
    def population(self):
        return self._data[DistrictColumns.POPULATION]

    @property
    def deviation(self):
        return self._data[DistrictColumns.DEVIATION]

    @property
    def pct_deviation(self):
        return self._data[DistrictColumns.PCT_DEVIATION]

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, value):
        self._description = value
        self.descriptionChanged.emit()

    @property
    def columns(self):
        return list(self._data.keys())

    def extend(self, columns: Iterable[str]):
        data = self._data
        addcols = [c for c in columns if c not in District.BASE_COLUMNS and c not in District.STATS_COLUMNS]
        self._data = dict.fromkeys(District.BASE_COLUMNS + addcols + District.STATS_COLUMNS)
        self._data.update(data)

    @overload
    def update(self, data: "District"):
        ...

    @overload
    def update(self, data: dict[str, Any]):
        ...

    def update(self, data: Union["District", dict[str, Any]]):
        if isinstance(data, District):
            self._fid = data.fid
            data = data[:]

        newkeys = [k for k in data.keys() if k not in District.BASE_COLUMNS + District.STATS_COLUMNS]
        self._data = dict.fromkeys(District.BASE_COLUMNS + newkeys + District.STATS_COLUMNS) | self._data | data


class Unassigned(District):
    def __init__(self, district: Literal[0] = 0, fid=-1, **kwargs):
        assert district == 0
        super().__init__(district, fid, **kwargs)

    def __setitem__(self, key: Union[str, int, slice], value: Any):
        raise IndexError(tr("'{key}' field is readonly for Unassigned goegraphies").format(key=key))

    def update(self, data: Union["District", dict[str, Any]]):
        super().update(data)

        self._data[DistrictColumns.NAME] = tr("Unassigned")
        self._data[DistrictColumns.MEMBERS] = None
        self._data[DistrictColumns.DEVIATION] = None
        self._data[DistrictColumns.PCT_DEVIATION] = None
        self._data['polsbypopper'] = None
        self._data['reock'] = None
        self._data['convexhul'] = None
