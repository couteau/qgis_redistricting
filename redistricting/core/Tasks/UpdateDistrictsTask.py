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
from distutils.version import LooseVersion
import math
from typing import Iterable, List, Set, Union, TYPE_CHECKING
from contextlib import closing
import fiona
import pandas as pd
import geopandas as gpd
from shapely import wkt
from qgis.core import (
    QgsGeometry,
    QgsFeatureRequest,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsAggregateCalculator,
    QgsTask
)
from qgis.utils import spatialite_connect
from ..utils import tr
from .UpdateTask import AggregateDataTask
from ._debug import debug_thread
from ._exception import CancelledError

if TYPE_CHECKING:
    from .. import RedistrictingPlan, Field


class AggregateDistrictDataTask(AggregateDataTask):
    """Task to aggregate the plan summary data and geometry in the background"""

    def __init__(
        self,
        plan: 'RedistrictingPlan',
        updateDistricts: Iterable[int] = None,
        includeDemographics=True,
        includeGeometry=True,
        useBuffer=True
    ):
        super().__init__(plan, tr('Calculating district geometry and metrics'))
        self.distList = plan.districts[:]

        self.geoFields: List['Field'] = plan.geoFields
        self.numDistricts: int = plan.numDistricts
        self.geoPackagePath = plan.geoPackagePath

        self.updateDistricts: Set[int] = None \
            if updateDistricts is None or set(updateDistricts) == set(range(0, self.numDistricts+1)) \
            else set(updateDistricts)

        self.includeGeometry = includeGeometry
        self.includeDemographics = includeDemographics
        self.useBuffer = useBuffer

        self.districts: Union[pd.DataFrame, gpd.GeoDataFrame] = None
        self.totalPop = 0
        self.splits = {}
        self.calculateSplits = True

    def run(self) -> bool:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        debug_thread()

        try:
            crs = self.assignLayer.crs()

            if self.updateDistricts:
                context = QgsExpressionContext()
                context.appendScopes(
                    QgsExpressionContextUtils.globalProjectLayerScopes(self.assignLayer))

                flt = f"{self.distField} in ({','.join(str(d) for d in self.updateDistricts)})"  # pylint: disable=not-an-iterable
                if 0 in self.updateDistricts:  # pylint: disable=unsupported-membership-test
                    flt += f" or {self.distField} is null"

                agg = QgsAggregateCalculator(self.assignLayer)
                agg.setFilter(flt)
                self.total, success = agg.calculate(QgsAggregateCalculator.Count, self.geoIdField, context)
                if not success:
                    self.total = 100

                if self.includeDemographics:
                    self.total *= 2

                fields = self.assignLayer.fields()
                gIndex = fields.lookupField(self.geoIdField)
                dIndex = fields.lookupField(self.distField)
                cols = [self.geoIdField, self.distField]

                request = QgsFeatureRequest()
                if self.includeGeometry:
                    cols.append('geometry')
                else:
                    request.setFlags(QgsFeatureRequest.NoGeometry)

                request.setExpressionContext(context)
                request.setFilterExpression(flt)
                request.setSubsetOfAttributes(cols, fields)

                if self.useBuffer:
                    features = self.assignLayer.getFeatures(request)
                else:
                    features = self.assignLayer.dataProvider().getFeatures(request)

                if self.includeGeometry:
                    datagen = (self.getData([f[gIndex], f[dIndex], wkt.loads(f.geometry().asWkt())]) for f in features)
                else:
                    datagen = (self.getData([f[gIndex], f[dIndex]]) for f in features)
                df = gpd.GeoDataFrame.from_records(datagen, index=self.geoIdField, columns=cols)
                if self.includeGeometry:
                    df.set_geometry(df.geometry, inplace=True, crs=crs.toWkt())
                    self.setProgress(95)
            else:
                cols = [self.geoIdField, self.distField]
                total = self.assignLayer.featureCount()
                self.total = total * 2 if self.includeDemographics else total
                chunkSize = max(100, 10 ** (math.ceil(math.log10(total)) - 2))
                self.count = 0
                df: gpd.GeoDataFrame = None
                while self.count < total:
                    s = slice(self.count, min(self.count+chunkSize, total))
                    f = gpd.read_file(
                        self.geoPackagePath,
                        layer='assignments',
                        rows=s,
                        geometry='geometry',
                        include_fields=cols
                    )
                    df = f if df is None else pd.concat([df, f], copy=False)
                    self.count = s.stop
                    if self.isCanceled():
                        raise CancelledError()
                    self.setProgress(90 * self.count/self.total)
                df.set_index(self.geoIdField, drop=True, inplace=True)
                if LooseVersion(fiona.__version__) < LooseVersion('1.19'):
                    cols.append('geometry')
                    df.drop(columns=[col for col in df if col not in cols], inplace=True)

            # convert null values to 0 if the "unassigned" district is among those being aggregated
            if not self.updateDistricts or 0 in self.updateDistricts:  # pylint: disable=unsupported-membership-test
                df[self.distField] = pd.to_numeric(df[self.distField], errors='coerce').fillna(0).astype(int)

            if self.includeDemographics:
                context = QgsExpressionContext()
                context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))

                cols = [self.joinField]
                getters = [lambda f: f[self.joinField]]
                aggs = {}
                self.addPopFields(cols, getters, aggs, context)

                request = QgsFeatureRequest()
                if self.updateDistricts is not None:
                    request.setExpressionContext(context)
                    r = ','.join([f"'{geoid}'" for geoid in df.index])
                    request.setFilterExpression(f'{self.joinField} in ({r})')

                if not self.hasExpression():
                    request.setSubsetOfAttributes(cols, self.popLayer.fields())

                features = self.popLayer.getFeatures(request)

                datagen = (self.getData([getter(f) for getter in getters]) for f in features)
                dfpop = pd.DataFrame.from_records(datagen, index=self.joinField, columns=cols)
                df = pd.merge(df, dfpop, how='left', left_index=True, right_index=True, copy=False)

            if self.includeGeometry:
                self.districts: gpd.GeoDataFrame = df.dissolve(by=self.distField, aggfunc=aggs)

                geo: gpd.GeoSeries = self.districts['geometry'].to_crs('+proj=cea')
                area = geo.area

                self.districts['polsbypopper'] = 4 * math.pi * area / (geo.length**2)

                self.districts['reock'] = geo.apply(
                    lambda g:
                        g.area /
                        QgsGeometry.fromWkt(g.wkt).minimalEnclosingCircle()[0].area()
                )

                self.districts['convexhull'] = area / \
                    geo.convex_hull.area
            else:
                self.districts = df.groupby(by=self.distField).agg(aggs)

            self.setProgress(99)

            # calculate total population only if all districts are being aggregated
            if self.includeDemographics and self.updateDistricts is None:
                self.totalPop = int(self.districts[self.popField].sum())

            self.splits = {}
            if self.calculateSplits:
                with closing(spatialite_connect(self.geoPackagePath)) as db:
                    for field in self.geoFields:
                        sql = f'SELECT {field.fieldName}, COUNT(DISTINCT {self.distField}) AS splits ' \
                            f'FROM assignments GROUP BY {field.fieldName} HAVING splits > 1'
                        s = db.execute(sql).fetchall()
                        self.splits[field.fieldName] = s

            self.setProgress(100)
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

        return True

    def finished(self, result: bool):
        super().finished(result)

        if not result:
            return

        name = [self.distList[d].name if d in self.distList else d for d in self.districts.index.astype(str)]
        self.districts.insert(0, 'name', name)

        members = [0 if d == 0 else self.distList[d].members if d in self.distList else 1 for d in self.districts.index]
        self.districts.insert(1, 'members', members)

        with closing(spatialite_connect(self.geoPackagePath)) as db:
            fields = {f: f"GeomFromText(:{f})" if f == "geometry" else f":{f}" for f in list(self.districts.columns)}

            sql = f"DELETE FROM districts WHERE NOT district IN ({','.join(self.districts.index.astype(str))})"
            db.execute(sql)

            data = [d._asdict() for d in self.districts.itertuples()]
            if self.includeGeometry:
                for d in data:
                    d['geometry'] = wkt.dumps(d['geometry'])

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


class CalculateCutEdgesTask(QgsTask):
    """Task to calculate the cut edges of a plan in the background"""

    def __init__(
        self,
        plan: 'RedistrictingPlan',
        geoField=None,
        useBuffer=True
    ):
        super().__init__(plan, tr('Calculating district geometry and metrics'))
        self.useBuffer = useBuffer
        self.assignLayer = plan.assignLayer
        self.distField = plan.distField
        self.geoIdField = plan.geoIdField

        if geoField != self.geoIdField and self.assignLayer.fields().lookupField(geoField) != -1:
            self.geoField = geoField
        else:
            self.geoField = None

        self.cutEdges = []
        self.exception = None

    def run(self):
        try:
            if self.useBuffer:
                features = self.assignLayer.getFeatures()
            else:
                features = self.assignLayer.dataProvider().getFeatures()

            gIndex = self.assignLayer.fields().lookupField(self.geoField)
            dIndex = self.assignLayer.fields().lookupField(self.distField)
            if self.geoField:
                fIndex = self.assignLayer.fields().lookupField(self.geoField)
                datagen = ([f[gIndex], f[fIndex], f[dIndex], wkt.loads(f.geometry().asWkt())] for f in features)
                cols = [self.geoField, self.geoField, self.distField, 'geometry']
            else:
                datagen = ([f[gIndex], f[dIndex], wkt.loads(f.geometry().asWkt())] for f in features)
                cols = [self.geoField, self.distField, 'geometry']

            df: gpd.GeoDataFrame = gpd.GeoDataFrame.from_records(
                datagen,
                index=self.geoField,
                columns=cols)
            df.set_geometry(df.geometry, inplace=True, crs=self.assignLayer.crs().toWkt())

            if self.geoField:
                df = df.dissolve(by=self.geoField)

            try:
                # pylint: disable=import-outside-toplevel
                from gerrychain import Graph, Partition, updaters  # type: ignore
                # pylint: enable=import-outside-toplevel

                graph = Graph.from_geodataframe(df.to_crs('+proj=cea'), ignore_errors=True)
                partition = Partition(
                    graph,
                    assignment=self.distField,
                    updaters={"cut_edges": updaters.cut_edges}
                )
                self.cutEdges = partition['cut_edges']
            except ImportError:
                pass
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

        return True
