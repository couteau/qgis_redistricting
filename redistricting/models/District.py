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
from .columns import DistrictColumns


class District(QObject):
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

    def __init__(self, district: int, fid: int = -1, **kwargs):
        super().__init__()
        assert kwargs.pop(DistrictColumns.DISTRICT, district) == district
        scores = {
            'polsbypopper': kwargs.pop('polsbypopper', 0.0),
            'reock': kwargs.pop('reock', 0.0),
            'convexhull': kwargs.pop('convexhull', 0.0)
        }
        self._description = kwargs.pop("description", "")
        self._data = {
            DistrictColumns.DISTRICT: district,
            DistrictColumns.NAME: kwargs.pop(DistrictColumns.NAME, str(district)),
            DistrictColumns.MEMBERS: kwargs.pop(DistrictColumns.MEMBERS, 1),
            DistrictColumns.POPULATION: kwargs.pop(DistrictColumns.POPULATION, 0),
            DistrictColumns.DEVIATION: kwargs.pop(DistrictColumns.DEVIATION, 0),
            DistrictColumns.PCT_DEVIATION: kwargs.pop(DistrictColumns.PCT_DEVIATION, 0.0),


        } | kwargs | scores
        self._district = district
        self._fid = fid

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
        self._data = dict.fromkeys(columns)
        self.update(data)

    def update(self, data: dict[str, Any]):
        self._data.update({k: v for k, v in data.items() if k in self._data})


class Unassigned(District):
    def __init__(self, district: Literal[0] = 0, fid=-1, **kwargs):
        assert district == 0
        kwargs[DistrictColumns.NAME] = tr("Unassigned")
        kwargs[DistrictColumns.DEVIATION] = None
        kwargs[DistrictColumns.PCT_DEVIATION] = None
        super().__init__(district, fid, **kwargs)

    def __setitem__(self, key: Union[str, int, slice], value: Any):
        raise IndexError(tr("'{key}' field is readonly for Unassigned goegraphies").format(key=key))
