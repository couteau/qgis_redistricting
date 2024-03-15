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
    Literal,
    Optional,
    Sequence,
    Union,
    overload
)

import geopandas as gpd
import pandas as pd
from qgis.core import (
    Qgis,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsMessageLog,
    QgsTask,
    QgsVectorLayer
)

from ..layer import LayerReader
from ..sql import SqlAccess

if TYPE_CHECKING:
    from .. import (
        DataField,
        Field,
        RedistrictingPlan
    )


class AggregateDataTask(SqlAccess, QgsTask):
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
        self.totalPopulation = plan.totalPopulation
        self.ideal = plan.ideal
        self.districts = plan.districts
        self.count = 0
        self.total = 1
        self.exception = None
        self._prog_start = 0
        self._prog_stop = 100

    def setProgressIncrement(self, start: int, stop: int):
        super().setProgress(start)
        self._prog_start = start
        self._prog_stop = stop

    def setProgress(self, progress: float):
        super().setProgress(self._prog_start + progress*(self._prog_stop-self._prog_start)/100)

    def updateProgress(self, total, count):
        if total != 0:
            self.setProgress(min(100, 100*count/total))

    @overload
    def read_layer(
        self,
        layer,
        columns: Optional[list[str]] = ...,
        order: Optional[str] = ...,
        read_geometry: Literal[False] = ...,
        chunksize: int = ...
    ) -> pd.DataFrame:
        ...

    @overload
    def read_layer(
        self,
        layer,
        columns: Optional[list[str]] = ...,
        order: Optional[str] = ...,
        read_geometry: Literal[True] = ...,
        chunksize: int = ...
    ) -> gpd.GeoDataFrame:
        ...

    def read_layer(
            self,
            layer: QgsVectorLayer,
            columns: Optional[list[str]] = None,
            order: Optional[str] = None,
            read_geometry: bool = True,
            chunksize: int = 0
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        reader = LayerReader(layer, self)
        return reader.read_layer(columns=columns, order=order, read_geometry=read_geometry, chunksize=chunksize)

    def loadPopData(self):
        cols = [self.popJoinField, self.popField]
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))
        for f in self.popFields:
            if f.isExpression:
                expr = QgsExpression(f.field)
                expr.prepare(context)
                cols += expr.referencedColumns()
            else:
                cols.append(f.field)

        for f in self.dataFields:
            if f.isExpression:
                expr = QgsExpression(f.field)
                expr.prepare(context)
                cols += expr.referencedColumns()
            else:
                cols.append(f.field)

        df = self.read_layer(
            self.popLayer,
            columns=cols,
            order=self.popJoinField,
            read_geometry=False
        )
        for f in self.popFields:
            if f.isExpression:
                df.loc[:, f.fieldName] = df.query(f.field)
        for f in self.dataFields:
            if f.isExpression:
                df.loc[:, f.fieldName] = df.query(f.field)

        return df

    def finished(self, result: bool):
        super().finished(result)
        if not result:
            if self.exception is not None:
                QgsMessageLog.logMessage(
                    f'{self.exception!r}', 'Redistricting', Qgis.Critical)
