# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RedistrictingPlan
        QGIS Redistricting Plugin - manage editing of assignments
                              -------------------
        begin                : 2022-05-25
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
from typing import TYPE_CHECKING, Dict, Union, Sized
from qgis.PyQt.QtCore import QVariant, QObject, pyqtSignal
from qgis.core import (
    Qgis,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFeatureIterator,
    QgsFeatureRequest,
    QgsFeedback,
    QgsMessageLog,
)

from .Utils import tr
if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class PlanAssignmentEditor(QObject):
    assignmentsChanged = pyqtSignal()

    def __init__(self, plan: RedistrictingPlan, parent: QObject = None):
        super().__init__(parent)
        self._plan = plan
        self._assignLayer = plan.assignLayer
        self._distField = plan._distField
        self._error = None
        self._errorLevel: Qgis.MessageLevel = 0
        self._undoStack = self._assignLayer.undoStack()
        self._undoStack.indexChanged.connect(self.undoChanged)

    def error(self):
        return (self._error, self._errorLevel)

    def _setError(self, error, level=Qgis.Warning):
        self._error = error
        self._errorLevel = level
        QgsMessageLog.logMessage(error, 'Redistricting', level)

    def _clearError(self):
        self._error = None

    def getDistFeatures(self, field, value, sourceDistrict=None):
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
        if f.type() == QVariant.String:
            flt = f"{field} = '{value}'"
        else:
            flt = f'{field} = {value}'

        if not sourceDistrict is None:
            if sourceDistrict == 0:
                flt += f' and ({self._distField} = 0 or {self._distField} is null)'
            else:
                flt += f' and {self._distField} = {sourceDistrict}'

        request.setExpressionContext(context)
        request.setFilterExpression(flt)
        request.setFlags(QgsFeatureRequest.NoGeometry)

        return self._assignLayer.getFeatures(request)

    def assignFeaturesToDistrict(
        self,
        features: Union[QgsFeatureIterator, Dict[int, QgsFeature]],
        district,
        oldDistrict=None,
        feedback: QgsFeedback = None
    ):
        self._clearError()

        fieldIndex = self._assignLayer.fields().indexOf(self._distField)
        if fieldIndex == -1:
            self._setError(
                tr('Error updating district assignment for {plan}: district field {field} not found in district layer.').
                format(plan=self._plan.name, field=self._distField)
            )
            return

        inTransaction = self._assignLayer.isEditable()
        if not inTransaction:
            self._assignLayer.startEditing()
            self._assignLayer.undoStack()

        try:
            if isinstance(features, QgsFeatureIterator):
                features = {f.id(): f for f in features}

            if isinstance(features, Sized):
                count = len(features)
                descrip = tr('Assign %d feature(s) to district %s') % (
                    count, str(district))
            else:
                count = 0
                descrip = tr('Assign features to district %s') % (
                    str(district))

            self._assignLayer.beginEditCommand(descrip)
            i = 0
            for f in features:
                self._assignLayer.changeAttributeValue(
                    f, fieldIndex, district, oldDistrict)
                i += 1
                if count:
                    progress = 100 * (i+1) / float(count)
                else:
                    progress = i
                if feedback:
                    feedback.setProgress(progress)

            self._assignLayer.endEditCommand()
        except:
            self._assignLayer.destroyEditCommand()
            # only delete the buffer on error if we were not already in a transaction --
            # otherwise we may discard prior, successful updates
            self._assignLayer.rollBack(not inTransaction)
            raise

    def _changed(self):
        self.assignmentsChanged.emit()

    def undoChanged(self, index):  # pylint: disable=unused-argument
        self._changed()

    def commitChanges(self):
        self._assignLayer.commitChanges(True)
        self._changed()

    def rollback(self):
        self._assignLayer.rollBack(True)
        self._changed()
