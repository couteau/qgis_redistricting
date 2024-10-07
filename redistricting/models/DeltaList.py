# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - manage list of pending assignments

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
    TYPE_CHECKING,
    Optional,
    Union,
    overload
)

import pandas as pd
from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)

if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class Delta:
    def __init__(self, index: int, dlist: "DeltaList"):
        self._list = dlist
        self._index = index

    def __getitem__(self, index):
        if isinstance(index, int) and 0 <= index < len(self._list.data.columns):
            return self._list.data.iloc[self._index, index]

        if isinstance(index, str) and index in self._list.data.columns:
            d = self._list.data.index[self._index]
            return self._list.data.loc[d, index]

        raise IndexError("Bad delta index")

    def __len__(self):
        return len(self._list.data.columns)

    def __eq__(self, other: "Delta"):
        return self._list == other._list and self._index == other._index

    @property
    def name(self):
        d = int(self._list.data.index[self._index])
        return self._list.districts[d].name

    @property
    def district(self):
        return int(self._list.data.index[self._index])


class DeltaList(QObject):
    updateStarted = pyqtSignal('PyQt_PyObject')
    updateComplete = pyqtSignal('PyQt_PyObject')

    def __init__(self, plan: "RedistrictingPlan", parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._plan = plan
        self.districts = plan.districts
        self._data: pd.DataFrame = None

    @overload
    def __getitem__(self, index: int) -> Delta:
        pass

    @overload
    def __getitem__(self, index: str) -> Union[Delta, pd.Series, None]:
        pass

    @overload
    def __getitem__(self, index: tuple) -> Union[int, str, float]:
        pass

    def __getitem__(self, index) -> Union[int, str, float, pd.Series, Delta, None]:
        if self._data is None:
            return None

        if isinstance(index, tuple):
            row, col = index
            value = self._data.iat[row, col]
            return value if not pd.isna(value) else None

        if isinstance(index, str):
            if index.isnumeric():
                index = int(index)
                if index in self._data.index:
                    i = self._data.index.get_loc(index)
                    return Delta(i, self)
                if 0 <= index <= self._plan.numDistricts:
                    return None
            elif index in self._data.columns:
                return list(self._data[index])

        elif isinstance(index, int):
            return Delta(index, self)

        raise IndexError()

    def __len__(self) -> int:
        return len(self._data) if self._data is not None else 0

    def __iter__(self):
        if self._data is not None:
            for index in range(len(self._data)):
                yield Delta(index, self)

    def __bool__(self):
        return self._data is not None and not self._data.empty

    def changedDistricts(self) -> list[int]:
        if self._data is not None:
            return list(self._data.index)

        return []

    @property
    def data(self):
        return self._data

    @property
    def plan(self):
        return self._plan

    def clear(self):
        self.updateStarted.emit(self._plan)
        self._data = None
        self.updateComplete.emit(self._plan)

    def update(self, data: pd.DataFrame):
        self.updateStarted.emit(self._plan)
        self._data = data
        self.updateComplete.emit(self._plan)
