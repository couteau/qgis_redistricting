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

from collections.abc import Iterable, Mapping, Sequence
from itertools import repeat
from typing import TYPE_CHECKING, Union

import geopandas as gpd
import pandas as pd
import shapely.ops
from qgis.PyQt.QtCore import QRunnable, QThreadPool
from shapely.geometry import MultiPolygon, Polygon

from ...models import DistrictColumns, MetricLevel, MetricTriggers
from ...models.metricslist import get_batches
from ...utils import spatialite_connect, tr
from ...utils.misc import camel_to_snake, quote_identifier
from ..districtio import DistrictReader
from ._debug import debug_thread
from .updatebase import AggregateDataTask

if TYPE_CHECKING:
    from ...models import RdsMetric, RdsPlan
    from ...models.lists import KeyedList


class DissolveWorker(QRunnable):
    def __init__(self, dist: int, geoms: Sequence[MultiPolygon], cb=None):
        super().__init__()
        self.dist = dist
        self.geoms = geoms
        self.merged = None
        self.callback = cb

    def run(self):
        debug_thread()

        self.merged = shapely.ops.unary_union(self.geoms)
        if isinstance(self.merged, Polygon):
            self.merged = MultiPolygon([self.merged])

        if self.callback:
            self.callback()


class AggregateDistrictDataTask(AggregateDataTask):
    """Task to aggregate the plan summary data and geometry in the background"""

    def __init__(
        self, plan: "RdsPlan", updateDistricts: Iterable[int] = None, includeDemographics=True, includeGeometry=True
    ):
        super().__init__(plan, tr("Calculating district geometry and metrics"))
        self.setDependentLayers([plan.distLayer, plan.assignLayer, plan.popLayer])
        self.geoPackagePath = plan.geoPackagePath

        self.updateDistricts: set[int] = (
            None
            if not updateDistricts or set(updateDistricts) == set(range(0, self.numDistricts + 1))
            else set(updateDistricts)
        )

        self.includeGeometry = includeGeometry
        self.includeDemographics = includeDemographics

        self.districtData: Union[pd.DataFrame, gpd.GeoDataFrame] = None

        self.metrics: KeyedList[RdsMetric] = plan.metrics.metrics
        trigger: MetricTriggers = 0
        if self.includeDemographics:
            trigger |= MetricTriggers.ON_UPDATE_DEMOGRAPHICS
        if self.includeGeometry:
            trigger |= MetricTriggers.ON_UPDATE_GEOMETRY
        self.trigger = trigger

    def disolveGeometry(self, update: gpd.GeoDataFrame):
        def dissolve_progress():
            nonlocal count, total
            count += 1
            self.updateProgress(total, count)

        g_geom = update[[self.distField, "geometry"]].groupby(self.distField)
        total = len(g_geom) + 1
        count = 0
        geoms: dict[int, shapely.MultiPolygon] = {}
        pool = QThreadPool()
        tasks: list[DissolveWorker] = []
        for g, v in g_geom["geometry"]:
            if g == 0:
                geoms[g] = None
                count += 1
                self.updateProgress(total, count)
            else:
                task = DissolveWorker(int(g), v.array, dissolve_progress)
                task.setAutoDelete(False)
                tasks.append(task)
                pool.start(task)

        pool.waitForDone()
        geoms |= {t.dist: t.merged for t in tasks}
        return geoms

    def saveDistricts(self):
        name = pd.Series(
            [self.districts.get(d).name if d in self.districts else str(d) for d in self.districtData.index],
            index=self.districtData.index,
        )
        members = pd.Series(
            [
                0 if d == 0 else self.districts.get(d).members if d in self.districts else 1
                for d in self.districtData.index
            ],
            index=self.districtData.index,
            dtype=int,
        )

        self.districtData = self.districtData.join(
            pd.DataFrame({DistrictColumns.NAME: name, DistrictColumns.MEMBERS: members})
        )

        with spatialite_connect(self.geoPackagePath) as db:
            # Account for districts with no assignments --
            # otherwise, they will never be updated in the database
            if self.updateDistricts is None:
                zero = set(range(0, self.numDistricts + 1)) - set(self.districtData.index)
            else:
                zero = self.updateDistricts - set(self.districtData.index)

            if zero:
                params = ",".join(repeat("?", len(zero)))
                sql = f"DELETE FROM districts WHERE {quote_identifier(self.distField)} IN ({params})"  # noqa: S608
                db.execute(sql, [str(d) for d in zero])
                db.commit()

            # Update existing dictricts
            fields = {
                quote_identifier(f): f"GeomFromText(:{f})" if f == "geometry" else f":{f}"
                for f in list(self.districtData.columns)
            }
            data = [d._asdict() for d in self.districtData.to_wkt().itertuples()]
            params = ",".join(f"{field} = {param}" for field, param in fields.items())
            sql = (
                "UPDATE districts "  # noqa: S608
                f"SET {params} "
                f"WHERE {quote_identifier(self.distField)} = :Index"
            )
            db.executemany(sql, data)
            db.commit()

            fields = {quote_identifier(self.distField): ":Index"} | fields
            sql = f"INSERT OR IGNORE INTO districts ({','.join(fields.keys())}) VALUES ({','.join(fields.values())})"  # noqa: S608
            db.executemany(sql, data)
            db.commit()

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
            reader = DistrictReader(self.plan.distLayer, self.distField, self.popField, self.plan.districtColumns)
            reader.loadDistricts(self.plan)
        except Exception as e:  # pylint: disable=broad-except
            raise RuntimeError(f"Failed to update district metrics: {e}") from e

    def run(self) -> bool:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        debug_thread()

        try:
            self.setProgressIncrement(0, 20)
            self.populationData = self.read_layer(self.assignLayer, read_geometry=self.includeGeometry).set_index(
                self.geoIdField
            )

            cols = [self.distField]
            if self.includeDemographics:
                self.setProgressIncrement(20, 40)
                popdf = self.loadPopData()
                self.populationData: gpd.GeoDataFrame = self.populationData.join(popdf)
                cols += [DistrictColumns.POPULATION, *self.popFields.keys(), *self.dataFields.keys()]
                self.totalPopulation = int(self.populationData[DistrictColumns.POPULATION].sum())

            self.setProgressIncrement(40, 90)
            if self.updateDistricts is not None:
                update = self.populationData[self.populationData[self.distField].isin(self.updateDistricts)]
            else:
                update = self.populationData

            if self.includeGeometry:
                geoms = self.disolveGeometry(update)
                update = update[cols].groupby(by=self.distField).sum()
                update["geometry"] = pd.Series(geoms)
                update = gpd.GeoDataFrame(update, geometry="geometry", crs=self.populationData.crs)

                # self.data = data.to_wkt()
                self.geometry = update["geometry"]
                self.districtData = update

                self.updateProgress(1, 1)
            else:
                update = update.drop(columns="geometry")
                total = len(update)
                self.districtData = update[cols].groupby(by=self.distField).sum()

                self.updateProgress(total, total)

            self.setProgressIncrement(90, 100)

            self.saveDistricts()

            self.calculateMetrics()

            return True
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

    def finished(self, result: bool):
        super().finished(result)

        if not result:
            return

        # Finish metrics calculations
        batches = self._get_batches_for_trigger(self.trigger)
        update_districts = False
        for b in batches:
            for metric in b:
                if metric.level() == MetricLevel.DISTRICT:
                    update_districts = True
                metric.finished(self.plan)

        if update_districts:
            self.saveDistrictMetrics()
