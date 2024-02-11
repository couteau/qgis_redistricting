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
    overload
)

import pandas as pd
from qgis.core import QgsCategorizedSymbolRenderer
from qgis.PyQt.QtGui import (
    QColor,
    QPalette
)

from .Delta import Delta

if TYPE_CHECKING:
    from .DistrictList import DistrictList


class District:
    def __init__(self, district: int, owner: DistrictList):
        self._district = district
        self._list = owner
        self._delta = None

    @overload
    def __getitem__(self, index: str | int) -> Any:
        ...

    @overload
    def __getitem__(self, index: slice) -> pd.Series:
        ...

    def __getitem__(self, key: int | str | slice):
        if isinstance(key, str) and key in self._list.data.columns:
            return self._list.data.at[self._district, key]

        if isinstance(key, int) and 0 <= key < len(self._list.data.columns):
            return self._list.data.iat[self._district, key]

        if isinstance(key, slice):
            return self._list.data.loc[self._district, key]

        raise IndexError(f"{key} not found in district")

    def __setitem__(self, key: int | str, value):
        if key in ("district", 0):
            raise ValueError("district field is read-only")

        if isinstance(key, str) and key in self._list.data.columns:
            self._list.data.at[self._district, key] = value
        elif isinstance(key, int) and 1 <= key < len(self._list.data.columns):
            self._list.data.iat[self._district, key] = value

    def __getattr__(self, key: str):
        try:
            self.__getitem__(key)
        except IndexError as e:
            raise AttributeError(f"{key} not found in plan") from e

    def isValid(self):
        lower, upper = self._list.idealRange(self["members"])
        return lower <= self["population"] <= upper

    @property
    def delta(self):
        return self._delta

    @delta.setter
    def delta(self, value: dict[str, int]):
        if value:
            self._delta = Delta(self._plan, self, value)
        else:
            self._delta = None

    @property
    def color(self):
        renderer = self._list.layer.renderer()
        if isinstance(renderer, QgsCategorizedSymbolRenderer):
            idx = renderer.categoryIndexForValue(self._district)
            if idx != -1:
                cat = renderer.categories()[idx]
                return QColor(cat.symbol().color())

        return QColor(QPalette().color(QPalette.Normal, QPalette.Window))
