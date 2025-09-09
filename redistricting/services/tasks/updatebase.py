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

from collections.abc import Mapping
from typing import Literal, Optional, Union, overload

import geopandas as gpd
import pandas as pd
from qgis.core import Qgis, QgsExpressionContext, QgsExpressionContextUtils, QgsMessageLog, QgsTask, QgsVectorLayer

from ...errors import CanceledError
from ...models import (
    DistrictColumns,
    MetricLevel,
    MetricTriggers,
    RdsDataField,
    RdsField,
    RdsGeoField,
    RdsMetric,
    RdsPlan,
)
from ...models.lists import KeyedList
from ...models.metricslist import get_batches
from ...utils import LayerReader, SqlAccess, camel_to_snake, tr
from ._debug import debug_thread


class UpdateMetricsTask(QgsTask):
    def __init__(
        self,
        plan: RdsPlan,
        trigger: MetricTriggers,
        populationData: pd.DataFrame,
        districtData: Optional[pd.DataFrame],
        geometry: Optional[gpd.GeoSeries],
    ):
        super().__init__(tr("Updating metrics"), QgsTask.Flag.AllFlags)
        self.plan = plan
        self.metrics: KeyedList[str, RdsMetric] = plan.metrics.metrics
        self.trigger = trigger
        self.populationData = populationData
        self.districtData = districtData
        self.geometry = gpd.GeoSeries.from_wkt(geometry.to_wkt(), crs=geometry.crs) if geometry is not None else None
        self.exception: Optional[Exception] = None

    def _get_batches_for_trigger(self, trigger: MetricTriggers):
        # pylint: disable=no-member
        metrics = {name: metric for name, metric in self.metrics.items() if metric.triggers() & trigger}
        ready = {m.name(): m for metric in metrics.values() for m in metric.depends() if not m.triggers() & trigger}

        return get_batches(metrics, ready)

    def calculateMetrics(self):
        """called in background thread to recalculate values of metrics"""
        batches = self._get_batches_for_trigger(self.trigger)

        for b in batches:
            for metric in b:
                if self.trigger & metric.triggers():
                    depends = {
                        m.name(): self.metrics[m.name()].value  # pylint: disable=unsubscriptable-object
                        for m in metric.depends()
                        if m.name() in self.metrics  # pylint: disable=unsupported-membership-test
                    }
                    metric.calculate(self.populationData, self.districtData, self.geometry, self.plan, **depends)

    def saveDistrictMetrics(self):
        """updates the district-level metrics in the plan's district layer"""

        def to_dict(value: Union[Mapping, pd.Series, pd.DataFrame]) -> dict:
            if isinstance(value, pd.Series):
                return value.to_dict()
            if isinstance(value, pd.DataFrame):
                return value.to_dict(orient="records")
            if isinstance(value, Mapping):
                return value

            raise TypeError("Unsupported type for serialization.")

        provider = self.plan.distLayer.dataProvider() if self.plan.distLayer else None
        if provider is None:
            raise RuntimeError("No district layer available to add the metric field.")

        dist_metrics: dict[str, Union[Mapping, pd.Series, pd.DataFrame]] = {
            provider.fieldNameIndex(camel_to_snake(m.name())): to_dict(m.value)
            for m in self.metrics  # pylint: disable=no-member
            if m.level() == MetricLevel.DISTRICT  # only update district level metrics
            and m.serialize()  # only update metrics that are meant to be serialized
            and m.triggers() & self.trigger  # only update if the metric is triggered
            and m.value is not None  # only update if the metric has a value
            # only update if the metric has a corresponding field in the district layer
            and provider.fieldNameIndex(camel_to_snake(m.name())) != -1
        }

        try:
            provider.changeAttributeValues(
                {
                    f.id(): {name: values.get(f[self.plan.distField]) for name, values in dist_metrics.items()}
                    for f in provider.getFeatures()
                }
            )  # reset the attributes

            self.plan.distLayer.reload()
        except Exception as e:  # pylint: disable=broad-except
            raise RuntimeError(f"Failed to update district metrics: {e}") from e

    def run(self):
        debug_thread()
        try:
            self.calculateMetrics()
            return True
        except Exception as e:
            self.exception = e
            return False

    def finished(self, result: bool):
        super().finished(result)
        if result:
            batches = self._get_batches_for_trigger(self.trigger)
            update_districts = False
            for b in batches:
                for metric in b:
                    if metric.level() == MetricLevel.DISTRICT:
                        update_districts = True
                    metric.finished(self.plan)

            if update_districts:
                self.saveDistrictMetrics()


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
        self.popFields: KeyedList[str, RdsField] = plan.popFields
        self.dataFields: KeyedList[str, RdsDataField] = plan.dataFields
        self.geoFields: KeyedList[str, RdsGeoField] = plan.geoFields
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

        popData = self.read_layer(self.popLayer, columns=cols, order=self.popJoinField, read_geometry=False)

        for f in self.popFields:
            if f.isExpression():
                popData.loc[:, f.fieldName] = popData.eval(f.field)
        for f in self.dataFields:
            if f.isExpression():
                popData.loc[:, f.fieldName] = popData.eval(f.field)

        return popData.drop(columns=remove).rename(columns={self.popField: str(DistrictColumns.POPULATION)})

    def finished(self, result: bool):
        super().finished(result)
        if not result:
            if self.exception is not None:
                QgsMessageLog.logMessage(f"{self.exception!r}", "Redistricting", Qgis.MessageLevel.Critical)
