# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - manage editing of assignments

        begin                : 2022-05-25
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
    Iterable,
    Optional,
    Union
)

import pandas as pd
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFeatureRequest,
    QgsMessageLog
)
from qgis.PyQt.QtCore import (
    QObject,
    QVariant,
    pyqtSignal
)

from ..utils import tr
from .Tasks import AggregatePendingChangesTask

if TYPE_CHECKING:
    from ..models import RedistrictingPlan


class PlanAssignmentEditor(QObject):
    assignmentsChanged = pyqtSignal("PyQt_PyObject")

    def __init__(self, plan: RedistrictingPlan, parent: QObject = None):
        super().__init__(parent)
        if not plan.isValid():
            raise ValueError()

        self._plan = plan
        self._assignLayer = plan._assignLayer
        self._distField = plan._distField
        self._undoStack = self._assignLayer.undoStack()
        self._error = None
        self._errorLevel: Qgis.MessageLevel = 0
        self._pendingTask: AggregatePendingChangesTask = None
        self._assignments: pd.DataFrame = None
        self._popData: pd.DataFrame = None

        self._assignLayer.afterCommitChanges.connect(self.commitChanges)
        self._assignLayer.afterRollBack.connect(self.rollback)
        self._undoStack.indexChanged.connect(self.undoChanged)

    def isUpdatingPending(self):
        return self._pendingTask is not None and self._pendingTask.status() < self._pendingTask.TaskStatus.Complete

    def updatePendingData(self):
        def taskCompleted():
            self._plan.delta.update(self._pendingTask.data)
            self._assignments = self._pendingTask.assignments
            self._popData = self._pendingTask.popData
            self._pendingTask = None

        def taskTerminated():
            if self._pendingTask.exception:
                self._setError(str(self._pendingTask.exception), Qgis.Warning)
            self._pendingTask = None

        if self._pendingTask and self._pendingTask.status() < self._pendingTask.TaskStatus.Complete:
            return self._pendingTask

        if not self._assignLayer or not self._assignLayer.editBuffer() or self._undoStack.index() == 0:
            self.clear()
            return None

        self._pendingTask = AggregatePendingChangesTask(self._plan, self._popData, self._assignments)
        self._pendingTask.taskCompleted.connect(taskCompleted)
        self._pendingTask.taskTerminated.connect(taskTerminated)
        QgsApplication.taskManager().addTask(self._pendingTask)
        return self._pendingTask

    def error(self):
        return (self._error, self._errorLevel)

    def _setError(self, error, level=Qgis.Warning):
        self._error = error
        self._errorLevel = level
        QgsMessageLog.logMessage(error, 'Redistricting', level)

    def _clearError(self):
        self._error = None

    def startEditCommand(self, msg: str = None):
        if not self._assignLayer.isEditable():
            self._assignLayer.startEditing()
            self._assignLayer.undoStack()

        if msg is None:
            msg = tr('Edit assignments')

        self._assignLayer.beginEditCommand(msg)

    def endEditCommand(self):
        self._assignLayer.endEditCommand()

    def cancelEditCommand(self):
        self._assignLayer.destroyEditCommand()

    def getDistFeatures(self, field, value: Union[Iterable[str], str], targetDistrict=None, sourceDistrict=None):
        self._clearError()

        if not self._assignLayer:
            return None

        f = self._assignLayer.fields().field(field)
        if not f:
            return None

        context = QgsExpressionContext()
        context.appendScopes(
            QgsExpressionContextUtils.globalProjectLayerScopes(self._assignLayer))
        request = QgsFeatureRequest()
        if isinstance(value, str):
            value = [value]

        if f.type() == QVariant.String:
            flt = ' and '.join(f"{field} = '{v}'" for v in value)
        else:
            flt = ' and '.join(f'{field} = {v}' for v in value)

        if sourceDistrict is not None:
            if sourceDistrict == 0:
                flt += f' and ({self._distField} = 0 or {self._distField} is null)'
            else:
                flt += f' and {self._distField} = {sourceDistrict}'
        elif targetDistrict is not None:
            if targetDistrict == 0:
                flt += f' and ({self._distField} is not null and {self._distField} != 0)'
            else:
                flt += f' and {self._distField} != {targetDistrict}'

        request.setExpressionContext(context)
        request.setFilterExpression(flt)
        request.setFlags(QgsFeatureRequest.NoGeometry)

        return self._assignLayer.getFeatures(request)

    def assignFeaturesToDistrict(
        self,
        features: Iterable[QgsFeature],
        district,
        oldDistrict=None,
        inTransaction=None
    ):
        self._clearError()

        fieldIndex = self._assignLayer.fields().indexOf(self._distField)
        if fieldIndex == -1:
            self._setError(
                tr('Error updating district assignment for {plan}: district field {field} not found in district layer.')
                .format(plan=self._plan.name, field=self._distField)
            )
            return

        if inTransaction is None:
            inTransaction = self._assignLayer.isEditable()

        try:
            for f in features:
                self._assignLayer.changeAttributeValue(
                    f.id(), fieldIndex, district, oldDistrict)
        except:
            # only delete the buffer on error if we were not already in a transaction --
            # otherwise we may discard prior, successful updates
            self._assignLayer.rollBack(not inTransaction)
            raise

    def changeAssignments(self, assignments: dict[int, Iterable[int]]):
        for dist, fids in assignments.items():
            self.assignFeaturesToDistrict(self._assignLayer.getFeatures(list(fids)), dist)

    def undoChanged(self, index):  # pylint: disable=unused-argument
        self.updatePendingData()
        self.assignmentsChanged.emit()

    def commitChanges(self):
        self._plan.delta.clear()

    def rollback(self):
        self._plan.delta.clear()


class AssignmentsService(QObject):
    editingStarted = pyqtSignal("PyQt_PyObject")
    editingStopped = pyqtSignal("PyQt_PyObject")
    assignmentsChanged = pyqtSignal("PyQt_PyObject")

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._editors: dict[RedistrictingPlan, PlanAssignmentEditor] = {}

    def startEditing(self, plan: RedistrictingPlan) -> PlanAssignmentEditor:
        if plan not in self._editors:
            self._editors[plan] = PlanAssignmentEditor(plan)
            self._editors[plan].assignmentsChanged.connect(self.assignmentsChanged)

        self.editingStarted.emit(plan)
        return self._editors[plan]

    def endEditing(self, plan: RedistrictingPlan):
        if plan in self._editors:
            del self._editors[plan]
            self.editingStopped.emit(plan)
