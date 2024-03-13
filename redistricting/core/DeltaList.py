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
    Union,
    overload
)

import pandas as pd
from qgis.core import (
    QgsApplication,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)

from .Tasks import AggregatePendingChangesTask

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
    updateTerminated = pyqtSignal('PyQt_PyObject')

    def __init__(self, plan: "RedistrictingPlan") -> None:
        super().__init__(plan)
        self._plan = plan
        self.districts = plan.districts

        self._assignLayer: QgsVectorLayer = None
        self._undoStack = None
        self._data: pd.DataFrame = None
        self._assignments: pd.DataFrame = None
        self._popData: pd.DataFrame = None
        self._pendingTask: AggregatePendingChangesTask = None

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
                return self._data[index]

        elif isinstance(index, int):
            return Delta(index, self)

        raise IndexError()

    def __len__(self) -> int:
        return len(self._data) if self._data is not None else 0

    def __iter__(self):
        if self._data is not None:
            for index in range(len(self._data)):
                yield Delta(index, self)

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

    def setAssignLayer(self, value: QgsVectorLayer):
        if self._assignLayer is not None:
            self._assignLayer.afterRollBack.disconnect(self.clear)
            self._assignLayer.afterCommitChanges.disconnect(self.clear)
            self._undoStack.indexChanged.disconnect(self.update)
            self._undoStack = None
        self._assignLayer = value
        if self._assignLayer is not None:
            self._assignLayer.afterRollBack.connect(self.clear)
            self._assignLayer.afterCommitChanges.connect(self.clear)
            self._undoStack = self._assignLayer.undoStack()
            self._undoStack.indexChanged.connect(self.update)

    def isUpdatingPending(self):
        return self._pendingTask is not None and self._pendingTask.status() < self._pendingTask.TaskStatus.Complete

    def clear(self):
        self.updateStarted.emit(self._plan)
        self._data = None
        self._assignments = None
        self.updateComplete.emit(self._plan)

    def update(self):
        def taskCompleted():
            self._data = self._pendingTask.data
            self._assignments = self._pendingTask.assignments
            self._popData = self._pendingTask.popData
            self._pendingTask = None
            self.updateComplete.emit(self._plan)

        def taskTerminated():
            self._pendingTask = None
            self.updateTerminated.emit(self._plan)

        if self._pendingTask and self._pendingTask.status() < self._pendingTask.TaskStatus.Complete:
            return self._pendingTask

        if not self._assignLayer or not self._assignLayer.editBuffer() or self._undoStack.index() == 0:
            self.clear()
            return None

        self.updateStarted.emit(self._plan)
        self._pendingTask = AggregatePendingChangesTask(self._plan, self._popData, self._assignments)
        self._pendingTask.taskCompleted.connect(taskCompleted)
        self._pendingTask.taskTerminated.connect(taskTerminated)
        QgsApplication.taskManager().addTask(self._pendingTask)
        return self._pendingTask
