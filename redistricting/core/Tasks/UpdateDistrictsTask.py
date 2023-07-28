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
import sqlite3
from contextlib import closing
from typing import (
    TYPE_CHECKING,
    Dict,
    Iterable,
    List,
    Set
)

import pandas as pd
import pyproj
from qgis.core import (
    QgsAggregateCalculator,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeatureRequest,
    QgsGeometry,
    QgsTask
)
from shapely import wkt
from shapely.geometry import MultiPolygon
from shapely.ops import transform

from ..utils import (
    spatialite_connect,
    tr
)
from ._debug import debug_thread
from ._exception import CancelledError
from .Sql import SqlAccess
from .UpdateTask import AggregateDataTask

if TYPE_CHECKING:
    from .. import (
        Field,
        RedistrictingPlan
    )

class Config:
    @staticmethod
    def calculateSplits():
        return True
    
    @staticmethod
    def splitPopulation():
        return True


class AggregateDistrictDataTask(SqlAccess, AggregateDataTask):
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

        self.setDependentLayers([plan.distLayer, plan.assignLayer, plan.popLayer])

        self.geoFields: List['Field'] = plan.geoFields
        self.numDistricts: int = plan.numDistricts
        self.geoPackagePath = plan.geoPackagePath

        self.updateDistricts: Set[int] = None \
            if updateDistricts is None or set(updateDistricts) == set(range(0, self.numDistricts+1)) \
            else set(updateDistricts)

        self.includeGeometry = includeGeometry
        self.includeDemographics = includeDemographics
        self.useBuffer = useBuffer

        self.districts: pd.DataFrame = None
        self.totalPop = 0
        self.splits = {}

    def getPopData(self, geoids: str, geoField=None, request: QgsFeatureRequest = None, cb = None):
        if geoField is None:
            geoField = self.joinField

        if self.isSQLCapable(self.popLayer):
            table = self.getTableName(self.popLayer)
            sql = f'SELECT SUM({self.popField}) AS {self.popField}'
            if self.vapField:
                sql += f', SUM({self.vapField}) AS {self.vapField}'
            if self.cvapField:
                sql += f', SUM({self.cvapField}) AS {self.cvapField}'
            for f in self.dataFields:
                sql += f', SUM({f.field}) AS {f.fieldName}'
            sql += f' FROM {table} WHERE {geoField} in ({geoids})'
            cur = self.executeSql(self.popLayer, sql)
            if cb: 
                cb(geoids.count(',') + 1)
            return dict(next(cur))

        if request is None:
            request = QgsFeatureRequest()
            if not self.hasExpression():
                request.setSubsetOfAttributes(self.cols, self.popLayer.fields())
            request.setFlags(QgsFeatureRequest.NoGeometry)

        pop = {
            self.popField: 0
        }
        if self.vapField:
            pop[self.vapField] = 0
        if self.cvapField:
            pop[self.cvapField] = 0
        for f in self.dataFields:
            pop[f.fieldName] = 0

        request.setFilterExpression(f'{geoField} in ({geoids})')
        for f in self.popLayer.getFeatures(request):
            for idx, fld in enumerate(pop):
                pop[fld] += self.getters[idx](f)
            if cb:
                cb(1)

        return pop
    
    def doSplits(self):
        self.splits = {}
        if Config.calculateSplits():
            with closing(spatialite_connect(self.geoPackagePath)) as db:
                for field in self.geoFields:
                    sql = f'SELECT {field.fieldName}, GROUP_CONCAT(DISTINCT QUOTE({self.distField})) AS districts, COUNT(DISTINCT {self.distField}) AS splits ' \
                        f'FROM assignments GROUP BY {field.fieldName} HAVING splits > 1'
                    
                    #s = pd.read_sql(sql, db, field.fieldName)
                    s = [dict(zip((field.fieldName, "districts", "splits"), row)) for row in db.execute(sql)]

                    if Config.splitPopulation():
                        for group in s:
                            g = group[field.fieldName]
                            pop = {}
                            for d in group["districts"].split(','):
                                sql = f"SELECT GROUP_CONCAT(QUOTE({self.geoIdField})) AS geoids FROM assignments WHERE {field.fieldName} = '{g}' AND {self.distField} = {d} GROUP BY {field.fieldName}, {self.distField}"
                                geoids = db.execute(sql).fetchone()[0]
                                pop[d] = self.getPopData(geoids)
                            group["districts"] = pop

                    self.splits[field.fieldName] = s

    def doMetrics(self):
        crs = self.assignLayer.crs()
            
        pp: Dict[int, float] = {}
        reock: Dict[int, float] = {}
        ch: Dict[int, float] = {}

        from_crs = pyproj.CRS(crs.authid())
        to_crs = pyproj.CRS('+proj=cea')
        project = pyproj.Transformer.from_crs(from_crs, to_crs, always_xy=True).transform
        for index, geom in self.districts['geometry'].items():
            geom: MultiPolygon
            cea: MultiPolygon = transform(project, geom)
            pp[index] = 4 * math.pi * cea.area / (cea.length**2)
            reock[index] = cea.area / QgsGeometry.fromWkt(cea.wkt).minimalEnclosingCircle()[0].area()
            ch[index] = cea.area / cea.convex_hull.area
        self.districts['polsbypopper'] = pd.Series(pp, dtype=float)
        self.districts['reock'] = pd.Series(reock, dtype=float)
        self.districts['convexhull'] = pd.Series(ch, dtype=float)

    def run(self) -> bool:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        def updateProgress(increment):
            nonlocal count
            count += increment

            self.setProgress(90*count/total)
            if self.isCanceled():
                raise CancelledError()

        debug_thread()

        try:
            count = 0
            if self.updateDistricts:
                context = QgsExpressionContext()
                context.appendScopes(
                    QgsExpressionContextUtils.globalProjectLayerScopes(self.assignLayer))

                flt = f"{self.distField} in ({','.join(str(d) for d in self.updateDistricts)})"  # pylint: disable=not-an-iterable
                if 0 in self.updateDistricts:  # pylint: disable=unsupported-membership-test
                    flt += f" or {self.distField} is null"

                agg = QgsAggregateCalculator(self.assignLayer)
                agg.setFilter(flt)
                total, success = agg.calculate(QgsAggregateCalculator.Count, self.geoIdField, context)
                if not success:
                    total = self.assignLayer.featureCount()

            else:
                total = self.assignLayer.featureCount()

            if self.includeDemographics:
                self.addPopFields()
                data = dict(zip(self.cols, [[] for _ in self.cols]))
            else:
                data = {}

            request = QgsFeatureRequest()
            if not self.hasExpression():
                request.setSubsetOfAttributes(self.cols, self.popLayer.fields())
            request.setFlags(QgsFeatureRequest.NoGeometry)

            with spatialite_connect(self.geoPackagePath) as db:
                db.row_factory = sqlite3.Row

                sql = f'SELECT {self.distField}, '
                if self.includeGeometry:
                    sql += 'ST_AsText(ST_UnaryUnion(ST_Collect(geometry))) as geometry, '
                sql += f'GROUP_CONCAT(QUOTE({self.geoIdField})) AS geoids ' \
                    'FROM assignments '
                if self.updateDistricts:
                    sql += f"WHERE {self.distField} IN ({','.join(str(d) for d in self.updateDistricts)}) "
                sql += f'GROUP BY {self.distField}'
                c = db.execute(sql)

                if self.includeGeometry:
                    data['geometry'] = []

                index = []
                for r in c:
                    index.append(r[self.distField])
                    if self.includeDemographics:
                        for p, v in self.getPopData(r['geoids'], request=request, cb=updateProgress).items():
                            data[p].append(v)
                    if self.includeGeometry:
                        data['geometry'].append(wkt.loads(r['geometry']))

            self.districts = pd.DataFrame(data, index=index)
            if self.includeGeometry:
                self.doMetrics()

            self.setProgress(99)

            # calculate total population only if all districts are being aggregated
            if self.includeDemographics and self.updateDistricts is None:
                self.totalPop = int(self.districts[self.popField].sum())

            self.doSplits()

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
            db.execute('SELECT EnableGpkgMode()')

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
            # pylint: disable=import-outside-toplevel
            import geopandas as gpd
            from gerrychain import (  # type: ignore
                Graph,
                Partition,
                updaters
            )

            # pylint: enable=import-outside-toplevel

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
