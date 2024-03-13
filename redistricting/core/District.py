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
from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Union,
    overload
)

import numpy as np
import pandas as pd
from qgis.core import QgsCategorizedSymbolRenderer
from qgis.PyQt.QtGui import (
    QColor,
    QPalette
)

if TYPE_CHECKING:
    from .DistrictList import DistrictList


class District:
    def __init__(self, district: int, lst: DistrictList):
        self._district = district
        self._data = lst._data
        self._index = self._data.index.get_loc(district)
        self._list = lst

    @overload
    def __getitem__(self, index: str | int) -> Any:
        ...

    @overload
    def __getitem__(self, index: slice) -> pd.Series:
        ...

    def __getitem__(self, key: Union[int, str, slice]):
        if isinstance(key, str) and key in self._data.columns:
            value = self._data.at[self._district, key]
        elif isinstance(key, int) and 0 <= key < len(self._list.columns):
            value = self._data.iat[self._index, key+1]
        elif isinstance(key, slice):
            key = self._list.columns[key]
            value = self._data.at[self._district, key]
        else:
            raise IndexError(f"{key} not found in district")

        if isinstance(value, np.integer):
            value = int(value)
        elif isinstance(value, np.floating):
            value = float(value)
        elif isinstance(value, np.bool_):
            value = bool(value)

        return value

    def __setitem__(self, key: Union[int, str], value: Any):
        if key == "district":
            raise IndexError("district field is readonly")

        if isinstance(key, int):
            if 0 <= key < len(self._list.columns):
                key = self._list.columns[key]
            else:
                raise IndexError(f"no item at index {key}")

        self._list.changeDistrictAttribute(self._district, key, value)

    def __getattr__(self, key: str):
        try:
            return self.__getitem__(key)
        except IndexError as e:
            raise AttributeError(f"{key} not found in district object") from e

    def __eq__(self, __value: "District"):
        return self._district == __value._district and \
            self._data.loc[self._district].equals(__value._data.loc[self._district])

    @property
    def name(self):
        value = self["name"]
        if not value:
            value = str(self._district)

        return value

    @name.setter
    def name(self, value):
        self["name"] = value

    @property
    def members(self):
        return self["members"]

    @members.setter
    def members(self, value):
        self["members"] = value

    @property
    def district(self):
        return self._district

    @property
    def population(self):
        if self._list.popField is None:
            return 0

        return self[self._list.popField]

    @property
    def ideal(self):
        return self._list.ideal * self["members"]

    @property
    def deviation(self):
        return self["deviation"]

    @property
    def description(self):
        return self["description"]

    @description.setter
    def description(self, value):
        self["description"] = value

    def isValid(self):
        if self._district == 0:
            return True
        lower, upper = self._list.idealRange(self["members"])
        return lower <= self.population <= upper

    @property
    def assignments(self):
        return self._list.getAssignments(self._district)

    @property
    def color(self):
        renderer = self._list.layer.renderer()
        if isinstance(renderer, QgsCategorizedSymbolRenderer):
            idx = renderer.categoryIndexForValue(self._district)
            if idx == -1:
                idx = 0

            cat = renderer.categories()[idx]
            return QColor(cat.symbol().color())

        return QColor(QPalette().color(QPalette.Normal, QPalette.Window))
