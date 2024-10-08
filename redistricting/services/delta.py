# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - monitor assignment changes and update delta object

        begin                : 2024-05-12
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
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from qgis.core import (
    QgsApplication,
    QgsTask
)
from qgis.PyQt.QtCore import (
    QObject,
    QSignalMapper,
    pyqtSignal
)

from ..models import (
    DeltaList,
    RdsPlan
)
from .errormixin import ErrorListMixin
from .planmgr import PlanManager
from .tasks.updatepending import AggregatePendingChangesTask


@dataclass
class DeltaUpdate:
    plan: RdsPlan
    assignments: pd.DataFrame = None
    popData: pd.DataFrame = None
    delta: DeltaList = None
    task: AggregatePendingChangesTask = None

    def __post_init__(self):
        if self.delta is None:
            self.delta = DeltaList()

    def clear(self):
        self.assignments = None
        self.task = None
        self.delta.clear()


class DeltaUpdateService(ErrorListMixin, QObject):
    updateStarted = pyqtSignal("PyQt_PyObject")
    updateCompleted = pyqtSignal("PyQt_PyObject", "PyQt_PyObject")
    updateTerminated = pyqtSignal("PyQt_PyObject", bool, "PyQt_PyObject")
    deltaStarted = pyqtSignal("PyQt_PyObject")
    deltaStopped = pyqtSignal("PyQt_PyObject")

    def __init__(self, planManager: PlanManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._planManager = planManager
        self._deltas: dict[RdsPlan, DeltaUpdate] = {}
        self._planManager.planAdded.connect(self.planAdded)
        self._planManager.planRemoved.connect(self.planRemoved)
        self._completeSignals = QSignalMapper(self)
        self._completeSignals.mappedObject.connect(self.deltaTaskCompleted)
        self._terminatedSignals = QSignalMapper(self)
        self._terminatedSignals.mappedObject.connect(self.deltaTaskTerminated)
        self._commitSignals = QSignalMapper(self)
        self._commitSignals.mappedObject.connect(self.commitChanges)
        self._rollbackSignals = QSignalMapper(self)
        self._rollbackSignals.mappedObject.connect(self.rollback)
        self._assignmentChangedSignals = QSignalMapper(self)
        self._assignmentChangedSignals.mappedObject.connect(self.undoChanged)
        self.editingStartedSignals = QSignalMapper(self)
        self.editingStartedSignals.mappedObject.connect(self.watchPlan)
        self.editingStoppedSignals = QSignalMapper(self)
        self.editingStoppedSignals.mappedObject.connect(self.unwatchPlan)

    def planAdded(self, plan: RdsPlan):
        if plan.assignLayer:
            self.editingStartedSignals.setMapping(plan.assignLayer, plan)
            self.editingStoppedSignals.setMapping(plan.assignLayer, plan)
            plan.assignLayer.editingStarted.connect(self.editingStartedSignals.map)
            plan.assignLayer.editingStopped.connect(self.editingStoppedSignals.map)

    def planRemoved(self, plan: RdsPlan):
        if plan.assignLayer:
            plan.assignLayer.editingStarted.disconnect(self.editingStartedSignals.map)
            plan.assignLayer.editingStopped.disconnect(self.editingStoppedSignals.map)
            self.editingStartedSignals.removeMappings(plan.assignLayer)
            self.editingStoppedSignals.removeMappings(plan.assignLayer)

    def watchPlan(self, plan: RdsPlan):
        if plan not in self._deltas:
            delta = DeltaUpdate(plan)
            self._commitSignals.setMapping(plan.assignLayer, plan)
            self._rollbackSignals.setMapping(plan.assignLayer, plan)
            self._assignmentChangedSignals.setMapping(plan.assignLayer.undoStack(), plan)
            plan.assignLayer.afterCommitChanges.connect(self._commitSignals.map)
            plan.assignLayer.afterRollBack.connect(self._rollbackSignals.map)
            plan.assignLayer.undoStack().indexChanged.connect(self._assignmentChangedSignals.map)
            self._deltas[plan] = delta
            self.deltaStarted.emit(plan)

    def unwatchPlan(self, plan: RdsPlan):
        if plan in self._deltas:
            self.deltaStopped.emit(plan)
            plan.assignLayer.afterCommitChanges.disconnect(self._commitSignals.map)
            plan.assignLayer.afterRollBack.disconnect(self._rollbackSignals.map)
            plan.assignLayer.undoStack().indexChanged.disconnect(self._assignmentChangedSignals.map)
            self._commitSignals.removeMappings(plan.assignLayer)
            self._rollbackSignals.removeMappings(plan.assignLayer)
            self._assignmentChangedSignals.removeMappings(plan.assignLayer.undoStack())
            del self._deltas[plan]

    def isUpdating(self, plan: RdsPlan):
        return plan in self._deltas \
            and self._deltas[plan].task is not None \
            and self._deltas[plan].task.status() < QgsTask.TaskStatus.Complete

    def deltaTaskCompleted(self, plan: RdsPlan):
        delta = self._deltas[plan]
        task = delta.task
        self._completeSignals.removeMappings(task)
        self._terminatedSignals.removeMappings(task)
        delta.assignments = task.assignments
        delta.popData = task.popData
        delta.delta.update(task.data)
        delta.task = None
        self.updateCompleted.emit(plan, delta.delta)

    def deltaTaskTerminated(self, plan):
        task = self._deltas[plan].task
        self._completeSignals.removeMappings(task)
        self._terminatedSignals.removeMappings(task)
        if task.exception:
            self.setError(str(task.exception))
        self._deltas[plan].task = None
        self.updateTerminated.emit(plan, task.isCanceled(), task.exception)

    def updatePendingData(self, plan: RdsPlan):
        if plan not in self._deltas:
            return None

        delta = self._deltas[plan]
        if delta.task is not None and delta.task.status() < QgsTask.TaskStatus.Complete:
            return delta.task

        if delta.plan.assignLayer is None \
                or delta.plan.assignLayer.editBuffer() is None \
                or delta.plan.assignLayer.undoStack().index() == 0:
            delta.delta.clear()
            return None

        task = AggregatePendingChangesTask(plan, delta.popData, delta.assignments)
        self._completeSignals.setMapping(task, plan)
        self._terminatedSignals.setMapping(task, plan)
        task.taskCompleted.connect(self._completeSignals.map)
        task.taskTerminated.connect(self._terminatedSignals.map)
        delta.task = task

        self.updateStarted.emit(plan)
        QgsApplication.taskManager().addTask(task)

        return task

    def undoChanged(self, plan: RdsPlan):  # pylint: disable=unused-argument
        self.updatePendingData(plan)

    def commitChanges(self, plan: RdsPlan):
        if plan in self._deltas:
            self._deltas[plan].clear()

    def rollback(self, plan: RdsPlan):
        if plan in self._deltas:
            self._deltas[plan].clear()

    def getDelta(self, plan: RdsPlan) -> DeltaList:
        if plan not in self._deltas:
            return None

        return self._deltas[plan].delta
