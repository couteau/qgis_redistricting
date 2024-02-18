# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - background task to aggregate district data

        begin                : 2022-06-01
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
    Sequence
)

import geopandas as gpd
import pandas as pd
from qgis.core import (
    Qgis,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsMessageLog,
    QgsTask,
    QgsVectorLayer
)

from ._exception import CancelledError

if TYPE_CHECKING:
    from .. import (
        DataField,
        Field,
        RedistrictingPlan
    )


class AggregateDataTask(QgsTask):
    """Task to aggregate the plan summary data and geometry in the background"""

    def __init__(self, plan: RedistrictingPlan, description):
        super().__init__(description, QgsTask.AllFlags)
        self.assignLayer: QgsVectorLayer = plan.assignLayer
        self.distLayer: QgsVectorLayer = plan.distLayer
        self.popLayer: QgsVectorLayer = plan.popLayer
        self.distField: str = plan.distField
        self.geoIdField: str = plan.geoIdField
        self.popJoinField: str = plan.popJoinField
        self.popField: str = plan.popField
        self.popFields: Sequence['Field'] = plan.popFields
        self.dataFields: Sequence['DataField'] = plan.dataFields
        self.count = 0
        self.total = 1
        self.exception = None
        self.cols = []
        self.getters = []
        self.aggs = {}
        self.context: QgsExpressionContext = None

    def updateProgress(self, total, count, start, stop):
        self.setProgress(start + (stop-start)*count/total)
        if self.isCanceled():
            raise CancelledError()

    def pd_read(self, source, fc, prog_start, prog_stop, **kwargs):
        df: gpd.GeoDataFrame = None
        if fc:
            divisions = 10
            chunksize = fc // divisions
            lastchunk = fc % divisions
            chunks = [slice(n * chunksize, (n+1) * chunksize) for n in range(divisions)] + [slice(fc-lastchunk, fc)]
            for s in chunks:
                chunk = gpd.read_file(source, rows=s, **kwargs)
                if df is None:
                    df = chunk
                else:
                    df = pd.concat([df, chunk])
                self.updateProgress(fc, s.stop, prog_start, prog_stop)
        else:
            df = gpd.read_file(source, **kwargs)
            self.updateProgress(len(df), len(df), prog_start, prog_stop)

        return df

    def hasExpression(self):
        for f in self.dataFields:
            if f.isExpression:
                return True

        return False

    def getData(self, data):
        if self.isCanceled():
            raise CancelledError()

        self.count += 1
        if self.count % 100 == 0:
            self.setProgress(90 * self.count/self.total)

        return data

    def getFieldValue(self, fld: 'DataField', context: QgsExpressionContext):
        return lambda f: fld.getValue(f, context)

    def addPopFields(self):
        self.context = QgsExpressionContext()
        self.context.appendScopes(
            QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer)
        )
        self.cols.append(self.popField)
        self.getters.append(lambda f: f[self.popField])
        self.aggs[self.popField] = 'sum'
        for fld in self.popFields:
            self.cols.append(fld.fieldName)
            self.getters.append(self.getFieldValue(fld, self.context))
            self.aggs[fld.fieldName] = 'sum'
        for fld in self.dataFields:
            self.cols.append(fld.fieldName)
            self.getters.append(self.getFieldValue(fld, self.context))
            self.aggs[fld.fieldName] = 'sum' if fld.isNumeric else 'first'

    def finished(self, result: bool):
        if not result:
            if self.exception is not None:
                QgsMessageLog.logMessage(
                    f'{self.exception!r}', 'Redistricting', Qgis.Critical)
