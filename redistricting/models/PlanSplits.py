# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - plan-wide stats

         begin                : 2024-02-18
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
from typing import (
    Any,
    Optional,
    Sequence
)

import pandas as pd
from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)

from .base import BaseModel


class SplitDistrict:
    def __init__(self, split: "SplitGeography", data: pd.DataFrame, idx: tuple[str, int], row: int):
        self._data = data
        self._split = split
        self._idx = idx
        self._row = row

    @property
    def geoid(self) -> str:
        return self._idx[0]

    @property
    def district(self) -> int:
        return self._idx[1]

    @property
    def row(self) -> int:
        return self._row

    @property
    def parent(self) -> "SplitGeography":
        return self._split

    @property
    def attributes(self) -> Sequence[Any]:
        return self

    def __len__(self) -> int:
        return len(self._data.columns) + 1 - int("__name" in self._data.columns)

    def __getitem__(self, index):
        if index == 0:
            return self.district
        else:
            col = self._data.columns[index-1]
            return self._data.loc[self._idx, col]


class SplitGeography:
    def __init__(self, lst: "SplitList", data: pd.DataFrame, geoid: str, row: int):
        self._list = lst
        self._data = data
        self._geoid = geoid
        self._row = row
        districts = data.loc[geoid].index
        self._districts = [
            SplitDistrict(self, data, (geoid, d), r) for r, d in enumerate(districts)
        ]

    def __len__(self):
        return len(self._districts)

    def __getitem__(self, index) -> SplitDistrict:
        return self._districts[index]

    @property
    def geoid(self):
        return self._geoid

    @property
    def row(self):
        return self._row

    @property
    def parent(self):
        return self._list

    @property
    def districts(self):
        districts = self._data.loc[self._geoid].index
        return ",".join(str(d) for d in districts)

    @property
    def name(self):
        if "__name" in self._data.columns:
            i = self._data.columns.get_loc("__name",)
            return self._data.loc[self._geoid].iat[0, i]

        return ""

    @property
    def attributes(self):
        return [f"{self.name} ({self.geoid})" if "__name" in self._data.columns else self.geoid, self.districts]


class SplitList(BaseModel):
    splitUpdating = pyqtSignal()
    splitUpdated = pyqtSignal()

    field: str
    data: pd.DataFrame

    def __init__(self, field: str, data: Optional[pd.DataFrame] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._field = field
        self._data = data or pd.DataFrame()
        self._splits = []
        if data is not None:
            self.makeSplits()

    @property
    def field(self) -> str:
        return self._field

    @property
    def data(self) -> pd.DataFrame:
        return self._data

    def makeSplits(self):
        self._splits = [
            SplitGeography(self, self._data, geoid, row)
            for row, geoid in enumerate(self._data.index.get_level_values(0).unique())
        ]

    def setData(self, data: pd.DataFrame):
        self.splitUpdating.emit()
        self._data = data
        self.makeSplits()
        self.splitUpdated.emit()

    def __len__(self):
        return len(self._splits)

    def __getitem__(self, index) -> SplitGeography:
        return self._splits[index]

    @property
    def attrCount(self):
        return len(self._data.columns) + 2 - int("__name" in self._data.columns)
