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

from ..models import RedistrictingPlan
from .ErrorList import ErrorListMixin
from .Tasks import AggregatePendingChangesTask


@dataclass
class DeltaUpdate:
    plan: RedistrictingPlan
    assignments: pd.DataFrame = None
    popData: pd.DataFrame = None
    task: AggregatePendingChangesTask = None


class DeltaUpdateService(ErrorListMixin, QObject):
    updateStarted = pyqtSignal("PyQt_PyObject")
    updateCompleted = pyqtSignal("PyQt_PyObject")
    updateTerminated = pyqtSignal("PyQt_PyObject", bool, "PyQt_PyObject")

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._deltas: dict[RedistrictingPlan, DeltaUpdate] = {}
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

    def watchPlan(self, plan: RedistrictingPlan):
        if plan not in self._deltas:
            delta = DeltaUpdate(plan)
            self._commitSignals.setMapping(plan.assignLayer, plan)
            self._rollbackSignals.setMapping(plan.assignLayer, plan)
            self._assignmentChangedSignals.setMapping(plan.assignLayer.undoStack(), plan)
            plan.assignLayer.afterCommitChanges.connect(self._commitSignals.map)
            plan.assignLayer.afterRollBack.connect(self._rollbackSignals.map)
            plan.assignLayer.undoStack().indexChanged.connect(self._assignmentChangedSignals.map)
            self._deltas[plan] = delta

    def unwatchPlan(self, plan: RedistrictingPlan):
        if plan in self._deltas:
            plan.assignLayer.afterCommitChanges.disconnect(self._commitSignals.map)
            plan.assignLayer.afterRollBack.disconnect(self._rollbackSignals.map)
            plan.assignLayer.undoStack().indexChanged.disconnect(self._assignmentChangedSignals.map)
            self._commitSignals.removeMappings(plan.assignLayer)
            self._rollbackSignals.removeMappings(plan.assignLayer)
            self._assignmentChangedSignals.removeMappings(plan.assignLayer.undoStack())
            del self._deltas[plan]

    def isUpdating(self, plan: RedistrictingPlan):
        return plan in self._deltas \
            and self._deltas[plan].task is not None \
            and self._deltas[plan].task.status() < self._pendingTask.TaskStatus.Complete

    def deltaTaskCompleted(self, plan: RedistrictingPlan):
        delta = self._deltas[plan]
        task = delta.task
        self._completeSignals.removeMappings(task)
        self._terminatedSignals.removeMappings(task)
        plan.delta.update(task.data)
        delta.assignments = task.assignments
        delta.popData = task.popData
        delta.task = None
        self.updateCompleted.emit(plan)

    def deltaTaskTerminated(self, plan):
        task = self._deltas[plan].task
        self._completeSignals.removeMappings(task)
        self._terminatedSignals.removeMappings(task)
        if task.exception:
            self.setError(str(task.exception))
        self._deltas[plan].task = None
        self.updateTerminated.emit(plan, task.isCanceled(), task.exception)

    def updatePendingData(self, plan: RedistrictingPlan):
        if plan not in self._deltas:
            return None

        delta = self._deltas[plan]
        if delta.task is not None and delta.task.status() < QgsTask.TaskStatus.Complete:
            return delta.task

        if delta.plan.assignLayer is None \
                or delta.plan.assignLayer.editBuffer() is None \
                or delta.plan.assignLayer.undoStack().index() == 0:
            plan.delta.clear()
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

    def undoChanged(self, plan: RedistrictingPlan):  # pylint: disable=unused-argument
        self.updatePendingData(plan)

    def commitChanges(self, plan: RedistrictingPlan):
        plan.delta.clear()

    def rollback(self, plan: RedistrictingPlan):
        plan.delta.clear()
