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

from typing import Literal, Optional, Union, overload
from collections.abc import Sequence

import geopandas as gpd
import pandas as pd
from qgis.core import Qgis, QgsExpressionContext, QgsExpressionContextUtils, QgsMessageLog, QgsTask, QgsVectorLayer

from ...errors import CanceledError
from ...models import DistrictColumns, MetricTriggers, RdsDataField, RdsField, RdsGeoField, RdsPlan
from ...utils import LayerReader, SqlAccess, tr
from ._debug import debug_thread


class UpdateMetricsTask(QgsTask):
    def __init__(self, plan: RdsPlan, trigger: MetricTriggers, populationData: pd.DataFrame, geometry: gpd.GeoSeries):
        super().__init__(tr("Updating metrics"), QgsTask.Flag.AllFlags)
        self.plan = plan
        self.trigger = trigger
        self.populationData = populationData
        self.geometry = geometry

    def run(self):
        debug_thread()
        self.plan.metrics.updateMetrics(self.trigger, self.populationData, self.geometry, self.plan)
        return True

    def finished(self, result: bool):
        super().finished(result)
        self.plan.metrics.updateFinished(self.trigger, self.plan)


class AggregateDataTask(SqlAccess, QgsTask):
    """Task to aggregate the plan summary data and geometry in the background"""

    def __init__(self, plan: RdsPlan, description: str):
        super().__init__(description, QgsTask.Flag.AllFlags)
        self.plan = plan
        self.numDistricts: int = plan.numDistricts
        self.numSeats: int = plan.numSeats
        self.totalPopulation = plan.totalPopulation
        self.ideal = plan.idealPopulation
        self.assignLayer: QgsVectorLayer = plan.assignLayer
        self.distLayer: QgsVectorLayer = plan.distLayer
        self.popLayer: QgsVectorLayer = plan.popLayer
        self.distField: str = plan.distField
        self.geoIdField: str = plan.geoIdField
        self.popJoinField: str = plan.popJoinField
        self.popField: str = plan.popField
        self.popFields: Sequence[RdsField] = plan.popFields
        self.dataFields: Sequence[RdsDataField] = plan.dataFields
        self.geoFields: Sequence[RdsGeoField] = plan.geoFields
        self.districts = plan.districts
        self.count = 0
        self.total = 1
        self.exception = None
        self._prog_start = 0
        self._prog_stop = 100
        self.populationData: pd.DataFrame = None
        self.geometry: gpd.GeoSeries = None

    def checkCanceled(self):
        if self.isCanceled():
            raise CanceledError()

    def setProgressIncrement(self, start: int, stop: int):
        super().setProgress(start)
        self._prog_start = start
        self._prog_stop = stop

    def setProgress(self, progress: float):
        super().setProgress(self._prog_start + progress * (self._prog_stop - self._prog_start) / 100)

    def updateProgress(self, total, count):
        if total != 0:
            self.setProgress(min(100, 100 * count / total))

    @overload
    def read_layer(
        self,
        layer,
        columns: Optional[list[str]] = ...,
        order: Optional[str] = ...,
        read_geometry: Literal[False] = ...,
        chunksize: int = ...,
    ) -> pd.DataFrame: ...

    @overload
    def read_layer(
        self,
        layer,
        columns: Optional[list[str]] = ...,
        order: Optional[str] = ...,
        read_geometry: Literal[True] = ...,
        chunksize: int = ...,
    ) -> gpd.GeoDataFrame: ...

    def read_layer(
        self,
        layer: QgsVectorLayer,
        columns: Optional[list[str]] = None,
        order: Optional[str] = None,
        read_geometry: bool = True,
        chunksize: int = 0,
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        reader = LayerReader(layer, self)
        return reader.read_layer(columns=columns, order=order, read_geometry=read_geometry, chunksize=chunksize)

    def loadPopData(self):
        cols = [self.popJoinField, self.popField]
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))
        remove = set()
        for f in self.popFields:
            f.prepare(context)
            new_cols = [c for c in f.expression.referencedColumns() if c not in cols]
            if f.isExpression():
                remove.update(new_cols)
            else:
                remove.difference_update(new_cols)

            cols.extend(new_cols)

        for f in self.dataFields:
            f.prepare(context)
            new_cols = [c for c in f.expression.referencedColumns() if c not in cols]
            if f.isExpression():
                remove.update(new_cols)
            else:
                remove.difference_update(new_cols)

            cols.extend(new_cols)

        popData = self.read_layer(self.popLayer, columns=cols, order=self.popJoinField, read_geometry=False).rename(
            columns={self.popField: str(DistrictColumns.POPULATION)}
        )

        for f in self.popFields:
            if f.isExpression():
                popData.loc[:, f.fieldName] = popData.eval(f.field)
        for f in self.dataFields:
            if f.isExpression():
                popData.loc[:, f.fieldName] = popData.eval(f.field)

        return popData.drop(columns=remove)

    def finished(self, result: bool):
        super().finished(result)
        if not result:
            if self.exception is not None:
                QgsMessageLog.logMessage(f"{self.exception!r}", "Redistricting", Qgis.MessageLevel.Critical)
