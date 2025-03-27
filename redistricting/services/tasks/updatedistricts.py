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
from collections.abc import (
    Iterable,
    Sequence
)
from typing import (
    TYPE_CHECKING,
    Union
)

import geopandas as gpd
import pandas as pd
import shapely.ops
from qgis.PyQt.QtCore import (
    QRunnable,
    QThreadPool
)
from shapely import wkt
from shapely.geometry import (
    MultiPolygon,
    Polygon
)

from ...models import DistrictColumns
from ...models.metricslist import MetricTriggers
from ...utils import (
    spatialite_connect,
    tr
)
from ..districtio import DistrictReader
from ._debug import debug_thread
from .updatebase import AggregateDataTask

if TYPE_CHECKING:
    from ...models import (
        RdsGeoField,
        RdsPlan
    )


class DissolveWorker(QRunnable):
    def __init__(self, dist: int, geoms: Sequence[MultiPolygon], cb=None):
        super().__init__()
        self.dist = dist
        self.geoms = geoms
        self.merged = None
        self.callback = cb

    def run(self):
        debug_thread()
        try:
            self.merged = shapely.ops.unary_union(self.geoms)
            if isinstance(self.merged, Polygon):
                self.merged = MultiPolygon([self.merged])
        except:  # pylint: disable=bare-except
            pass

        if self.callback:
            self.callback()


class AggregateDistrictDataTask(AggregateDataTask):
    """Task to aggregate the plan summary data and geometry in the background"""

    def __init__(
        self,
        plan: 'RdsPlan',
        updateDistricts: Iterable[int] = None,
        includeDemographics=True,
        includeGeometry=True
    ):
        super().__init__(plan, tr('Calculating district geometry and metrics'))
        self.distList = plan.districts[:]

        self.setDependentLayers([plan.distLayer, plan.assignLayer, plan.popLayer])

        self.geoFields: Sequence['RdsGeoField'] = plan.geoFields
        self.numDistricts: int = plan.numDistricts
        self.numSeats: int = plan.numSeats
        self.geoPackagePath = plan.geoPackagePath

        self.updateDistricts: set[int] = None \
            if not updateDistricts or set(updateDistricts) == set(range(0, self.numDistricts+1)) \
            else set(updateDistricts)

        self.includeGeometry = includeGeometry
        self.includeDemographics = includeDemographics
        self.trigger: MetricTriggers = 0
        if self.includeDemographics:
            self.trigger |= MetricTriggers.ON_UPDATE_DEMOGRAPHICS
        if self.includeGeometry:
            self.trigger |= MetricTriggers.ON_UPDATE_GEOMETRY

        self.districtData: Union[pd.DataFrame, gpd.GeoDataFrame] = None

    def run(self) -> bool:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        def dissolve_progress():
            nonlocal count, total
            count += 1
            self.updateProgress(total, count)

        debug_thread()

        try:
            self.setProgressIncrement(0, 20)
            self.populationData = self.read_layer(self.assignLayer, read_geometry=self.includeGeometry)
            self.populationData.set_index(self.geoIdField, inplace=True)

            cols = [self.distField]
            if self.includeDemographics:
                self.setProgressIncrement(20, 40)
                popdf = self.loadPopData()
                self.populationData: gpd.GeoDataFrame = self.populationData.join(popdf)
                cols += [DistrictColumns.POPULATION] + [f.fieldName for f in self.popFields] + \
                    [f.fieldName for f in self.dataFields]
                self.totalPopulation = int(self.populationData[DistrictColumns.POPULATION].sum())

            self.setProgressIncrement(40, 90)
            if self.updateDistricts is not None:
                update = self.populationData[self.populationData[self.distField].isin(self.updateDistricts)]
            else:
                update = self.populationData

            if self.includeGeometry:
                data = update[cols].groupby(by=self.distField).sum()
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

                data["geometry"] = pd.Series(geoms)
                data = gpd.GeoDataFrame(data, geometry="geometry", crs=self.populationData.crs)

                count += 1
                self.updateProgress(total, count)

                # self.data = data.to_wkt()
                self.geometry = data["geometry"]
                data["wkt_geom"] = data["geometry"].apply(wkt.dumps)
                data = data.drop(columns="geometry").rename(columns={"wkt_geom": "geometry"})
                self.districtData = data
            else:
                update.drop(columns="geometry", inplace=True)
                total = len(update)
                self.districtData = update[cols].groupby(by=self.distField).sum()

                self.updateProgress(total, total)

            self.setProgressIncrement(90, 100)

            name = pd.Series(
                [
                    self.distList[d].name if d in self.distList else str(d)
                    for d in self.districtData.index
                ],
                index=self.districtData.index
            )
            members = pd.Series(
                [
                    None if d == 0
                    else self.distList[d].members if d in self.distList
                    else 1
                    for d in self.districtData.index
                ],
                index=self.districtData.index
            )

            if self.includeDemographics:
                ideal = round(self.totalPopulation / self.numSeats)
                deviation = self.districtData[DistrictColumns.POPULATION].sub(members * ideal)
                pct_dev = deviation.div(members * ideal)
                df = pd.DataFrame(
                    {DistrictColumns.NAME: name,
                     DistrictColumns.MEMBERS: members,
                     DistrictColumns.DEVIATION: deviation,
                     DistrictColumns.PCT_DEVIATION: pct_dev}
                )
            else:
                df = pd.DataFrame({DistrictColumns.NAME: name, DistrictColumns.MEMBERS: members})

            self.districtData = self.districtData.join(df)

            self.updateMetrics(self.trigger)

            return True
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

    def finished(self, result: bool):
        super().finished(result)

        if not result:
            return

        self.finishMetrics(self.trigger)

        with spatialite_connect(self.geoPackagePath) as db:
            fields = {f: f"GeomFromText(:{f})" if f == "geometry" else f":{f}" for f in list(self.districtData.columns)}

            # Account for districts with no assignments --
            # otherwise, they will never be updated in the database
            if self.updateDistricts is None:
                zero = set(range(0, self.numDistricts+1)) - set(self.districtData.index)
            else:
                zero = self.updateDistricts - set(self.districtData.index)

            if zero:
                sql = f"DELETE FROM districts WHERE {self.distField} IN ({','.join(str(d) for d in zero)})"
                db.execute(sql)
                db.commit()

            data = [d._asdict() for d in self.districtData.itertuples()]
            sql = "UPDATE districts " \
                f"SET {','.join([f'{field} = {param}' for field, param in fields.items()])} " \
                f"WHERE {self.distField} = :Index"
            db.executemany(sql, data)
            db.commit()

            fields = {self.distField: ':Index'} | fields
            sql = f"INSERT OR IGNORE INTO districts ({','.join(fields)}) " \
                f"VALUES ({','.join(fields.values())})"
            db.executemany(sql, data)
            db.commit()

            reader = DistrictReader(self.plan.distLayer, self.distField, self.popField, self.plan.districtColumns)
            reader.loadDistricts(self.plan)

        self.distLayer.reload()
