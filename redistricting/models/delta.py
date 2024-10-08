# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - manage list of pending assignments

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
from typing import (
    Optional,
    Union,
    overload
)

import pandas as pd
from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)


class Delta:
    def __init__(self, district: int, data: pd.DataFrame):
        self._district = district
        self._data = data

    def __getitem__(self, index):
        if isinstance(index, int) and 0 <= index < len(self._data.columns):
            i = self._data.index.get_loc(self._district)
            return self._data.iloc[i, index]

        if isinstance(index, str) and index in self._data.columns:
            return self._data.loc[self._district, index]

        raise IndexError("Bad delta index")

    def __len__(self):
        return len(self._data.columns)

    @property
    def district(self):
        return self._district

    @property
    def name(self):
        return str(self._district)


class DeltaList(QObject):
    updateStarted = pyqtSignal()
    updateComplete = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.setData(None)

    @overload
    def __getitem__(self, index: int) -> Delta:
        pass

    @overload
    def __getitem__(self, index: str) -> Union[Delta, pd.Series, None]:
        pass

    @overload
    def __getitem__(self, index: tuple[int, int]) -> Union[int, str, float]:
        pass

    def __getitem__(self, index: Union[str, int, tuple[int, int]]) -> Union[int, str, float, pd.Series, Delta, None]:
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
                    return self._deltaDict[index]
            elif index in self._data.columns:
                return list(self._data[index])

        elif isinstance(index, int):
            return self._delta[index]

        raise IndexError()

    def __len__(self) -> int:
        return len(self._data) if self._data is not None else 0

    def __iter__(self):
        return iter(self._delta)

    def __bool__(self):
        return self._data is not None and not self._data.empty

    def __eq__(self, other: 'DeltaList'):
        if other is None:
            return False

        if not isinstance(other, DeltaList):
            return NotImplemented

        if self._data is None:
            return False

        return self._data.equals(other._data)

    def setData(self, data: Optional[pd.DataFrame]):
        self._data = data
        if data is not None:
            self._delta = [Delta(d, data) for d in data.index]
            self._deltaDict = {d.district: d for d in self._delta}
        else:
            self._delta: list[Delta] = []
            self._deltaDict: dict[int, Delta] = {}

    def clear(self):
        self.updateStarted.emit()
        self.setData(None)
        self.updateComplete.emit()

    def update(self, data: pd.DataFrame):
        self.updateStarted.emit()
        self.setData(data)
        self.updateComplete.emit()
