# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RedistrictingPlan
        QGIS Redistricting Plugin - manage list of pending assignments
                              -------------------
        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, List
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import QgsApplication
import pandas as pd

from .Delta import Delta
from .Tasks import AggregatePendingChangesTask

if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class DeltaList(QObject):
    updating = pyqtSignal('PyQt_PyObject')
    updateComplete = pyqtSignal('PyQt_PyObject')
    updateTerminated = pyqtSignal('PyQt_PyObject')

    def __init__(self, plan: RedistrictingPlan, parent: QObject = None) -> None:
        super().__init__(parent)
        self._plan = plan
        self._districts = plan.districts
        # self._plan.assignmentsChanged.connect(self.update)
        self._undoStack = self._plan.assignLayer.undoStack()
        self._undoStack.indexChanged.connect(self.update)
        self._plan.assignLayer.afterCommitChanges.connect(self.update)
        self._plan.assignLayer.afterRollBack.connect(self.update)
        self._pendingTask = None

    def __getitem__(self, index) -> Delta:
        if self._districts.update():
            return None

        if isinstance(index, str) and index.isnumeric():
            if index in self._districts:
                return self._districts[index].delta

            if 0 <= int(index) <= self._plan.numDistricts:
                return None
        elif isinstance(index, int):
            return self.items[index]

        raise IndexError()

    def __len__(self) -> int:
        return sum(1 for d in self._districts if d.delta is not None)

    def __iter__(self) -> Iterator[Delta]:
        return iter(self.items)

    @property
    def plan(self):
        return self._plan

    @property
    def items(self) -> List[Delta]:
        return [d.delta for d in self._districts if d.delta is not None]

    def isUpdatingPending(self):
        return self._pendingTask is not None

    def clear(self):
        self.updating.emit(self._plan)
        for district in self._districts:
            district.delta = None
        self.updateComplete.emit(self._plan)

    def updateDistricts(self, data: pd.DataFrame):
        for dist, delta in data.iterrows():
            d = self._districts[str(dist)]
            if d is None:
                assert d != 0
                d = self._districts.addDistrict(dist)
            d.delta = delta.to_dict()

    def update(self):
        def taskCompleted():
            self.updateDistricts(self._pendingTask.data)
            self._pendingTask = None
            self.updateComplete.emit(self._plan)

        def taskTerminated():
            self._pendingTask = None
            self.updateTerminated.emit(self._plan)

        if self._pendingTask:
            return self._pendingTask

        if not self._plan.assignLayer.editBuffer() or \
                len(self._plan.assignLayer.editBuffer().changedAttributeValues()) == 0:
            self.clear()
            return None

        self.updating.emit(self._plan)
        self._pendingTask = AggregatePendingChangesTask(self._plan, self._districts.update())
        self._pendingTask.taskCompleted.connect(taskCompleted)
        self._pendingTask.taskTerminated.connect(taskTerminated)
        QgsApplication.taskManager().addTask(self._pendingTask)
        return self._pendingTask
