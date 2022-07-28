# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - background task to calculate pending changes

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
from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING
import pandas as pd
from qgis.core import (
    QgsTask,
    QgsFeatureRequest,
    QgsExpressionContext,
    QgsExpressionContextUtils,
)
from ..Utils import tr
from ._debug import debug_thread
from .UpdateTask import AggregateDataTask

if TYPE_CHECKING:
    from .. import RedistrictingPlan


class AggregatePendingChangesTask(AggregateDataTask):
    def __init__(self, plan: RedistrictingPlan, updateTask: QgsTask = None):
        super().__init__(plan, tr('Computing pending changes'))
        self.data = None
        self.updateTask = updateTask
        if self.updateTask:
            self.updateTask.taskCompleted.connect(self.clearUpdateTask)
            self.updateTask.taskTerminated.connect(self.clearUpdateTask)

    def clearUpdateTask(self):
        self.updateTask = None

    def run(self):
        debug_thread()

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
            aggs = {}
            self.addPopFields(cols, getters, aggs, context)

            request = QgsFeatureRequest()
            request.setExpressionContext(context)
            r = ','.join([f"'{geoid}'" for geoid in pending.index])
            request.setFilterExpression(f'{self.joinField} in ({r})')

            datagen = ([getter(f) for getter in getters]
                       for f in self.popLayer.getFeatures(request))
            dfpop = pd.DataFrame.from_records(datagen, index=self.joinField, columns=cols)
            pending = pd.merge(pending, dfpop, how='left', left_index=True, right_index=True)

            newdist = pending.groupby(f'new_{self.distField}').agg(aggs)
            olddist = pending.groupby(f'old_{self.distField}').agg(aggs)
            del pending

            self.data = newdist.sub(olddist, fill_value=0)
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

        if self.updateTask:
            self.updateTask.waitForFinished(0)

        return True
