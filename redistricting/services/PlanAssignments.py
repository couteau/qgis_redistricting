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

import itertools
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    Iterator,
    Optional,
    Sequence,
    Union,
    overload
)

from qgis.core import (
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFeatureRequest,
    QgsVectorLayerEditPassthrough,
    QgsVectorLayerFeatureIterator
)
from qgis.PyQt.QtCore import (
    QObject,
    QSignalMapper,
    pyqtSignal
)

from ..utils import tr

if TYPE_CHECKING:
    from ..models import RdsPlan


class PlanAssignmentEditor(QObject):
    assignmentsChanged = pyqtSignal("PyQt_PyObject")

    def __init__(self, plan: RdsPlan, parent: QObject = None):
        super().__init__(parent)
        if not plan.isValid():
            raise ValueError()

        self._plan = plan
        self._assignLayer = plan.assignLayer
        self._distField = plan.distField
        self._fieldIndex = self._assignLayer.fields().indexOf(self._distField)
        if self._fieldIndex == -1:
            raise RuntimeError(
                tr('Error updating district assignment for {plan}: district field {field} not found in district layer.')
                .format(plan=self._plan.name, field=self._distField)
            )

        self._undoStack = self._assignLayer.undoStack()
        self._undoStack.indexChanged.connect(self.undoChanged)

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
        context.appendScope(QgsExpressionContextUtils.layerScope(self._assignLayer))
        request = QgsFeatureRequest()
        request.setExpressionContext(context)
        request.setFilterExpression(f"{self._distField} = {district}")
        request.setFlags(QgsFeatureRequest.NoGeometry)
        request.setSubsetOfAttributes([])
        for f in self._assignLayer.getFeatures(request):
            self._assignLayer.changeAttributeValue(f.id(), self._fieldIndex, newDistrict, district)

    def getDistFeatures(self, field: str, value: Union[Iterable[Any], Any], targetDistrict=None, sourceDistrict=None):
        if not self._assignLayer:
            return None

        if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
            value = [value]

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

        expression = QgsExpression(flt)
        if expression.hasParserError():
            return None

        context = QgsExpressionContext()
        context.appendScope(QgsExpressionContextUtils.layerScope(self._assignLayer))
        if not expression.prepare(context):
            return None

        request = QgsFeatureRequest(expression, context)
        request.setFlags(QgsFeatureRequest.NoGeometry)

        return self._assignLayer.getFeatures(request)

    @overload
    def assignFeaturesToDistrict(
        self,
        features: Iterable[QgsFeature],
        district
    ):
        ...

    @overload
    def assignFeaturesToDistrict(
        self,
        featureIds: Iterable[int],
        district: int
    ):
        ...

    def assignFeaturesToDistrict(
        self,
        features: Union[Iterable[QgsFeature], Iterable[int]],
        district
    ):
        # determine type of iterable elements
        if isinstance(features, Sequence):
            if len(features) > 0:
                if isinstance(features[0], int):
                    features = self._assignLayer.getFeatures(features)
        elif not isinstance(features, QgsVectorLayerFeatureIterator):
            if not isinstance(features, Iterator):
                features = iter(features)

            f = next(features, None)
            if f is None:
                return

            if isinstance(f, int):
                # int-iterator convert to feature iterator (so we can get the old value for undo purposes)
                features = self._assignLayer.getFeatures([f, *features])
            else:
                # push the peeked value back on the iterator
                features = itertools.chain([f], features)

        try:
            inTransaction = self._assignLayer.isEditable()
            if not inTransaction:
                self._assignLayer.startEditing()

            for f in features:
                self._assignLayer.changeAttributeValue(
                    f.id(), self._fieldIndex, district, f[self._fieldIndex])

            if not inTransaction:
                self._assignLayer.commitChanges(True)
        except:
            # only delete the buffer on error if we were not already in a transaction --
            # otherwise we may discard prior, successful updates
            self._assignLayer.rollBack(not inTransaction)
            raise

    def undoChanged(self, index):  # pylint: disable=unused-argument
        self.assignmentsChanged.emit(self._plan)

    def runQuery(self, query: str):
        buffer = self._assignLayer.editBuffer()
        if isinstance(buffer, QgsVectorLayerEditPassthrough):
            buffer.update(query)


class AssignmentsService(QObject):
    editingStarted = pyqtSignal("PyQt_PyObject")
    editingStopped = pyqtSignal("PyQt_PyObject")
    assignmentsChanged = pyqtSignal("PyQt_PyObject")

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._editors: dict[RdsPlan, PlanAssignmentEditor] = {}
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
            self._endEditSignals.setMapping(plan.assignLayer, plan)
            plan.assignLayer.afterCommitChanges.connect(self._endEditSignals.map)
            plan.assignLayer.afterRollBack.connect(self._endEditSignals.map)

            self.editingStarted.emit(plan)

        return self._editors[plan]

    def endEditing(self, plan: RdsPlan):
        if plan in self._editors:
            del self._editors[plan]
            plan.assignLayer.afterCommitChanges.disconnect(self._endEditSignals.map)
            plan.assignLayer.afterRollBack.disconnect(self._endEditSignals.map)
            self._endEditSignals.removeMappings(plan.assignLayer)

            self.editingStopped.emit(plan)
