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
    Any,
    Iterable,
    Optional,
    Union
)

import pandas as pd
from qgis.core import (
    Qgis,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFeatureRequest,
    QgsMessageLog
)
from qgis.PyQt.QtCore import (
    QObject,
    QSignalMapper,
    QVariant,
    pyqtSignal
)

from ..utils import tr
from .DeltaUpdate import DeltaUpdateService

if TYPE_CHECKING:
    from ..models import RdsPlan


class PlanAssignmentEditor(QObject):
    assignmentsChanged = pyqtSignal("PyQt_PyObject")

    def __init__(self, plan: RdsPlan, parent: QObject = None):
        super().__init__(parent)
        if not plan.isValid():
            raise ValueError()

        self._plan = plan
        self._assignLayer = plan._assignLayer
        self._distField = plan._distField
        self._undoStack = self._assignLayer.undoStack()
        self._error = None
        self._errorLevel: Qgis.MessageLevel = 0
        self._assignments: pd.DataFrame = None
        self._popData: pd.DataFrame = None

        self._undoStack.indexChanged.connect(self.undoChanged)

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

    def reassignDistrict(self, district: int, newDistrict: int = 0):
        context = QgsExpressionContext()
        context.appendScopes(
            QgsExpressionContextUtils.globalProjectLayerScopes(self._assignLayer))
        request = QgsFeatureRequest()
        request.setExpressionContext(context)
        request.setFilterExpression(f"{self._distField} = {district}")
        request.setFlags(QgsFeatureRequest.NoGeometry)
        request.setSubsetOfAttributes([self._distField], self._assignLayer.fields())
        findex = self._assignLayer.fields().indexFromName(self._distField)

        f: QgsFeature
        for f in self._assignLayer.getFeatures(request):
            self._assignLayer.changeAttributeValue(f.id(), findex, newDistrict, district)

    def getDistFeatures(self, field, value: Union[Iterable[Any], Any], targetDistrict=None, sourceDistrict=None):
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
            flt = ' and '.join(f'{field} = {v!r}' for v in value)

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
        self.assignmentsChanged.emit(self._plan)


class AssignmentsService(QObject):
    editingStarted = pyqtSignal("PyQt_PyObject")
    editingStopped = pyqtSignal("PyQt_PyObject")
    assignmentsChanged = pyqtSignal("PyQt_PyObject")

    def __init__(self, updateService: DeltaUpdateService, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._editors: dict[RdsPlan, PlanAssignmentEditor] = {}
        self._updateService = updateService
        self._endEditSignals = QSignalMapper(self)
        self._endEditSignals.mappedObject.connect(self.endEditing)

    def isEditing(self, plan: RdsPlan) -> bool:
        return plan in self._editors

    def getEditor(self, plan: RdsPlan) -> PlanAssignmentEditor:
        return self.startEditing(plan)

    def startEditing(self, plan: RdsPlan) -> PlanAssignmentEditor:
        if plan not in self._editors:
            self._editors[plan] = PlanAssignmentEditor(plan)
            self._editors[plan].assignmentsChanged.connect(self.assignmentsChanged)
            self._updateService.watchPlan(plan)
            self._endEditSignals.setMapping(plan.assignLayer, plan)
            plan.assignLayer.afterCommitChanges.connect(self._endEditSignals.map)
            plan.assignLayer.afterRollBack.connect(self._endEditSignals.map)

            self.editingStarted.emit(plan)

        return self._editors[plan]

    def endEditing(self, plan: RdsPlan):
        if plan in self._editors:
            del self._editors[plan]
            self._updateService.unwatchPlan(plan)
            plan.assignLayer.afterCommitChanges.disconnect(self._endEditSignals.map)
            plan.assignLayer.afterRollBack.disconnect(self._endEditSignals.map)
            self._endEditSignals.removeMappings(plan.assignLayer)
            self.editingStopped.emit(plan)
