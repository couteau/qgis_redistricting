# -*- coding: utf-8 -*-
"""QGIS Redistricting plugin utility functions and background tasks

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org

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

from typing import Any, Dict, TYPE_CHECKING
import pandas as pd
from qgis.core import (
    Qgis,
    QgsTask,
    QgsMessageLog,
    QgsFeatureRequest,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsVectorLayer,

)
from ..Utils import tr
from ._debug import debug_thread

if TYPE_CHECKING:
    from .. import RedistrictingPlan, DataField


class AggregatePendingChangesTask(QgsTask):
    def __init__(self, plan: RedistrictingPlan, updateTask: QgsTask = None):
        super().__init__(tr('Calculating pending changes'), QgsTask.AllFlags)
        self.assignLayer: QgsVectorLayer = plan.assignLayer
        self.popLayer: QgsVectorLayer = plan.popLayer
        self.distField = plan.distField
        self.geoIdField = plan.geoIdField
        self.joinField = plan.joinField
        self.popField = plan.popField
        self.vapField = plan.vapField
        self.cvapField = plan.cvapField
        self.dataFields = plan.dataFields
        self.data = None
        self.exception = None
        self.updateTask = updateTask
        if self.updateTask:
            self.updateTask.taskCompleted.connect(self.clearUpdateTask)
            self.updateTask.taskTerminated.connect(self.clearUpdateTask)

    def clearUpdateTask(self):
        self.updateTask = None

    def run(self):
        debug_thread()

        def getFieldValue(fld: DataField, context: QgsExpressionContext):
            return lambda f: fld.getValue(f, context)

        def addPopFields(cols: list, getters: list, context: QgsExpressionContext):
            cols.append(self.popField)
            getters.append(lambda f: f[self.popField])
            if self.vapField:
                cols.append(self.vapField)
                getters.append(lambda f: f[self.vapField])
            if self.cvapField:
                cols.append(self.cvapField)
                getters.append(lambda f: f[self.cvapField])
            cols.extend(
                fld.fieldName for fld in self.dataFields
            )
            getters.extend(
                getFieldValue(fld, context) for fld in self.dataFields
            )

        try:
            dindex = self.assignLayer.fields().lookupField(self.distField)
            if dindex == -1:
                return False
            gindex = self.assignLayer.fields().lookupField(self.geoIdField)
            if gindex == -1:
                return False

            flt: Dict[int, Dict[int, Any]] = {
                k: v for k, v in self.assignLayer.editBuffer().changedAttributeValues().items() if dindex in v}

            request = QgsFeatureRequest(list(flt))
            request.setSubsetOfAttributes([gindex, dindex])
            datagen = ([f.attribute(gindex), f.attribute(dindex)]
                       for f in self.assignLayer.getFeatures(request))
            new = pd.DataFrame.from_records(
                datagen, columns=[self.geoIdField, f'new_{self.distField}'], index=self.geoIdField)
            datagen = ([f.attribute(gindex), f.attribute(dindex)]
                       for f in self.assignLayer.dataProvider().getFeatures(request))
            old = pd.DataFrame.from_records(
                datagen, columns=[self.geoIdField, f'old_{self.distField}'], index=self.geoIdField)

            pending = pd.merge(new, old, how='outer', left_index=True, right_index=True)
            pending = pending[pending[f'new_{self.distField}'] != pending[f'old_{self.distField}']]
            del new
            del old

            if len(pending) == 0:
                self.data = pending
                return True

            context = QgsExpressionContext()
            context.appendScopes(
                QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))

            cols = [self.joinField]
            getters = [lambda f: f[self.joinField]]
            addPopFields(cols, getters, context)

            request = QgsFeatureRequest()
            request.setExpressionContext(context)
            r = ','.join([f"'{geoid}'" for geoid in pending.index])
            request.setFilterExpression(f'{self.joinField} in ({r})')

            datagen = ([getter(f) for getter in getters]
                       for f in self.popLayer.getFeatures(request))
            dfpop = pd.DataFrame.from_records(datagen, index=self.joinField, columns=cols)
            pending = pd.merge(pending, dfpop, how='left', left_index=True, right_index=True)

            newdist = pending.groupby(f'new_{self.distField}').sum()
            newdist.drop(columns=f'old_{self.distField}', inplace=True)
            olddist = pending.groupby(f'old_{self.distField}').sum()
            olddist.drop(columns=f'new_{self.distField}', inplace=True)
            del pending

            data = newdist.sub(olddist, fill_value=0)

            self.data = data
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

        if self.updateTask:
            self.updateTask.waitForFinished(0)

        return True

    def finished(self, result: bool):
        if not result:
            if self.exception is not None:
                QgsMessageLog.logMessage(f'{self.exception!r}',
                                         'Redistricting', Qgis.Critical)
