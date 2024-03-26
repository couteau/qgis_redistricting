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
import math
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
import pyproj
import shapely.ops
from packaging import version
from qgis.core import (
    QgsAggregateCalculator,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeatureRequest,
    QgsGeometry
)
from qgis.PyQt.QtCore import (
    QRunnable,
    QThreadPool
)
from shapely import wkt
from shapely.geometry import (
    MultiPolygon,
    Polygon
)

from ...utils import (
    spatialite_connect,
    tr
)
from ._debug import debug_thread
from .UpdateTask import AggregateDataTask

if TYPE_CHECKING:
    from ...models import (
        GeoField,
        RedistrictingPlan
    )


class Config:
    @staticmethod
    def calculateSplits():
        return True

    @staticmethod
    def splitPopulation():
        return True


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
        plan: 'RedistrictingPlan',
        updateDistricts: Iterable[int] = None,
        includeDemographics=True,
        includeGeometry=True,
        includSplits=True
    ):
        super().__init__(plan, tr('Calculating district geometry and metrics'))
        self.distList = plan.districts[:]

        self.setDependentLayers([plan.distLayer, plan._assignLayer, plan.popLayer])

        self.geoFields: Sequence['GeoField'] = plan.geoFields
        self.numDistricts: int = plan.numDistricts
        self.numSeats: int = plan.numSeats
        self.geoPackagePath = plan.geoPackagePath

        self.updateDistricts: set[int] = None \
            if not updateDistricts or set(updateDistricts) == set(range(0, self.numDistricts+1)) \
            else set(updateDistricts)

        self.includeGeometry = includeGeometry
        self.includeDemographics = includeDemographics
        self.includeSplits = includSplits

        self.data: pd.DataFrame
        self.splits = {}
        self.cutEdges = None

    def calcCutEdges(self, df: gpd.GeoDataFrame, distField) -> Union[int, None]:
        try:
            # pylint: disable-next=import-outside-toplevel
            from gerrychain import (  # type: ignore
                Graph,
                Partition,
                updaters
            )

            graph = Graph.from_geodataframe(df.to_crs('+proj=cea'), ignore_errors=True)
            partition = Partition(
                graph,
                assignment=distField,
                updaters={"cut_edges": updaters.cut_edges}
            )
            return partition['cut_edges']
        except ImportError:
            return None

    def getSplitNames(self, field: 'GeoField', geoids: Iterable[str]):
        ref = field.layer.referencingRelations(field.index)[0]
        name_layer = ref.referencedLayer()
        name_join_field = ref.resolveReferencedField(field.field)

        ctx = QgsExpressionContext()
        ctx.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(name_layer))

        expr = QgsExpression(f"""{name_join_field} in ({','.join(f"'{i}'" for i in geoids)})""")

        request = QgsFeatureRequest(expr, ctx)
        request.setSubsetOfAttributes([name_layer.fields().lookupField(name_join_field), field.nameField.index])
        request.setInvalidGeometryCheck(QgsFeatureRequest.InvalidGeometryCheck.GeometryNoCheck)

        name_map = {feat[name_join_field]: feat[field.nameField.index] for feat in name_layer.getFeatures(request)}

        return pd.Series(name_map.values(), index=name_map.keys(), name="__name", )

    def calcSplits(self, data: pd.DataFrame, cols: list[str]):
        total = len(self.geoFields) + 1
        self.splits = {}
        for field in self.geoFields:
            g = data.dropna(subset=[field.fieldName])[[field.fieldName] + cols].groupby([field.fieldName])
            splits_data = g.filter(lambda x: x[self.distField].nunique() > 1)

            splitpop = splits_data[[field.fieldName] + cols] \
                .groupby([field.fieldName, self.distField]) \
                .sum()

            if field.nameField and field.index and field.layer.referencingRelations(field.index):
                names = self.getSplitNames(field, splitpop.index.get_level_values(0).unique())
                splitpop = splitpop\
                    .reset_index(level=1) \
                    .join(names) \
                    .set_index('district', append=True) \
                    .sort_values(by="__name")
            else:
                splitpop = splitpop.sort_index()

            self.splits[field.fieldName] = splitpop
            self.updateProgress(total, len(self.splits))

        self.cutEdges = self.calcCutEdges(data, self.distField)
        self.updateProgress(total, total)

    def calcDistrictMetrics(self, data: gpd.GeoDataFrame):
        cea_crs = pyproj.CRS('+proj=cea')
        cea: gpd.GeoSeries = data.geometry.to_crs(cea_crs)
        area = cea.area

        data['polsbypopper'] = 4 * math.pi * area / (cea.length**2)
        if version.parse(gpd.__version__) < version.parse('1.0.0'):
            data['reock'] = cea.apply(lambda g: g.area / QgsGeometry.fromWkt(g.wkt).minimalEnclosingCircle()[0].area())
        else:
            data['reock'] = area / cea.minimum_bounding_circle().area
        data['convexhull'] = area / cea.convex_hull.area

    def calcTotalPopulation(self, data: pd.DataFrame, cols: list[str]):
        if self.popField in cols:
            self.totalPopulation = data[self.popField].sum()
        else:
            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))
            agg = QgsAggregateCalculator(self.popLayer)
            totalPop, success = agg.calculate(QgsAggregateCalculator.Sum, self.popField, context)
            if success:
                self.totalPopulation = int(totalPop)

    def run(self) -> bool:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        def dissolve_progress():
            nonlocal count, total
            count += 1
            self.updateProgress(total, count)

        debug_thread()

        try:
            self.setProgressIncrement(0, 20)
            assign = self.read_layer(self.assignLayer, read_geometry=self.includeGeometry)
            assign.set_index(self.geoIdField, inplace=True)

            cols = [self.distField]
            if self.includeDemographics:
                self.setProgressIncrement(20, 40)
                popdf = self.loadPopData()
                assign: gpd.GeoDataFrame = assign.join(popdf)
                cols += [self.popField] + [f.fieldName for f in self.popFields] + [f.fieldName for f in self.dataFields]
                self.totalPopulation = int(assign[self.popField].sum())

            self.setProgressIncrement(40, 50)
            if self.includeSplits:
                self.calcSplits(assign, cols)

            self.setProgressIncrement(50, 100)
            if self.includeGeometry:
                if self.updateDistricts is not None:
                    assign = assign[assign[self.distField].isin(self.updateDistricts)]
                data = assign[cols].groupby(by=self.distField).sum()
                g_geom = assign[[self.distField, "geometry"]].groupby(self.distField)
                total = len(g_geom)
                count = 0
                geoms = {}
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
                data = gpd.GeoDataFrame(data, geometry="geometry", crs=assign.crs)

                self.calcDistrictMetrics(data)

                # self.data = data.to_wkt()
                data["wkt_geom"] = data["geometry"].apply(wkt.dumps)
                data = data.drop(columns="geometry").rename(columns={"wkt_geom": "geometry"})
                self.data = data
            else:
                assign.drop(columns="geometry", inplace=True)
                if self.updateDistricts is not None:
                    assign = assign[assign[self.distField].isin(self.updateDistricts)]
                total = len(assign)
                self.data = assign[cols].groupby(by=self.distField).sum()

                self.updateProgress(total, total)

            # Account for districts with no assignments --
            # otherwise, they will never be updated in the database
            if self.updateDistricts is None:
                zero = set(range(0, self.numDistricts+1)) - set(self.data.index)
            else:
                zero = self.updateDistricts - set(self.data.index)

            if zero:
                df = pd.DataFrame(0, index=list(zero), columns=self.data.columns)
                self.data = pd.concat([self.data, df]).sort_index()

            name = pd.Series(
                [
                    self.distList[d].name if d in self.distList else str(d)
                    for d in self.data.index
                ],
                index=self.data.index
            )
            members = pd.Series(
                [
                    None if d == 0
                    else self.distList[d].members if d in self.distList
                    else 1
                    for d in self.data.index
                ],
                index=self.data.index
            )

            if self.includeDemographics:
                ideal = round(self.totalPopulation / self.numSeats)
                deviation = self.data[self.popField].sub(members * ideal)
                pct_dev = deviation.div(members * ideal)
                df = pd.DataFrame({'name': name, 'members': members, 'deviation': deviation, 'pct_deviation': pct_dev})
            else:
                df = pd.DataFrame({'name': name, 'members': members})

            self.data = self.data.join(df)

            return True
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

    def finished(self, result: bool):
        super().finished(result)

        if not result:
            return

        with spatialite_connect(self.geoPackagePath) as db:
            fields = {f: f"GeomFromText(:{f})" if f == "geometry" else f":{f}" for f in list(self.data.columns)}

            data = [d._asdict() for d in self.data.itertuples()]

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

        self.distLayer.reload()
