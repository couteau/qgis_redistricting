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
import re
import shlex
from collections.abc import (
    Iterable,
    Sequence
)
from typing import (
    TYPE_CHECKING,
    Iterator,
    Union
)

import geopandas as gpd
import pandas as pd
import pyproj
from qgis.core import (
    QgsAggregateCalculator,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFeatureRequest
)

from ..utils import (
    spatialite_connect,
    tr
)
from ._debug import debug_thread
from .Sql import SqlAccess
from .UpdateTask import AggregateDataTask

if TYPE_CHECKING:
    from .. import (
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

        self.geoFields: Sequence['GeoField'] = plan.geoFields
        self.numDistricts: int = plan.numDistricts
        self.numSeats: int = plan.numSeats
        self.geoPackagePath = plan.geoPackagePath

        self.updateDistricts: set[int] = None \
            if updateDistricts is None or set(updateDistricts) == set(range(0, self.numDistricts+1)) \
            else set(updateDistricts)

        self.includeGeometry = includeGeometry
        self.includeDemographics = includeDemographics
        self.useBuffer = useBuffer

        self.data: pd.DataFrame
        self.totalPop = 0
        self.splits = {}
        self.cutEdges = None

    def loadPopData(self):
        def prog_attributes(f: QgsFeature):
            nonlocal count
            count += 1
            self.updateProgress(fc, count, 20, 40)
            return f.attributes()

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

        fc = self.popLayer.featureCount()
        for f in self.dataFields:
            if f.isExpression:
                expr = QgsExpression(f.field)
                expr.prepare(context)
                cols += expr.referencedColumns()
            else:
                cols.append(f.field)

        if self.popLayer.storageType() in ("GPKG", "OpenFileGDB"):
            database, params = self.popLayer.source().split('|', 1)
            lexer = shlex.shlex(params)
            lexer.whitespace_split = True
            lexer.whitespace = '&'
            params = dict(pair.split('=', 1) for pair in lexer)
            layer = params['layername']

            df: gpd.GeoDataFrame = self.pd_read(database, fc, prog_start=20, prog_stop=40, layer=layer, columns=cols)
        elif self.popLayer.dataProvider().name() in ('spatialite', 'SQLite'):
            params = dict(
                pair.split('=', 1) for pair in
                shlex.split(re.sub(r' \(\w+\)', '', self.popLayer.dataProvider().dataSourceUri(True)))
            )
            layer = params['table']
            df: gpd.GeoDataFrame = gpd.read_file(
                params["dbname"], fc, prog_start=20, prog_stop=40, layer=layer, columns=cols)
        elif self.popLayer.dataProvider().name() in ('postgis', 'postgres'):
            df: gpd.GeoDataFrame = gpd.read_file(self.popLayer.dataProvider().dataSourceUri(
                True), fc, prog_start=20, prog_stop=40, columns=cols)
        elif self.popLayer.storageType() in ("ESRI Shapefile", "GeoJSON"):
            df: gpd.GeoDataFrame = gpd.read_file(self.popLayer.source(), fc, prog_start=20, prog_stop=40, columns=cols)
        else:  # the slow fallback
            count = 0
            fields = self.popLayer.fields()
            indices = [fields.lookupField(c) for c in cols]
            if any((i == -1 for i in indices)):
                raise RuntimeError("Bad fields")
            req = QgsFeatureRequest()
            req.setSubsetOfAttributes(indices)
            gen = (prog_attributes(f) for f in self.popLayer.getFeatures(req))
            df = pd.DataFrame(gen, columns=cols)

        df.drop(columns=df.columns.difference(cols), inplace=True)
        df.set_index(self.popJoinField, inplace=True)
        for f in self.popFields:
            if f.isExpression:
                df[f.fieldName] = df.query(f.field)
        for f in self.dataFields:
            if f.isExpression:
                df[f.fieldName] = df.query(f.field)

        return df

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
        if field.nameField and field.index and field.layer.referencingRelations(field.index):
            ref = field.layer.referencingRelations(field.index)[0]
            name_layer = ref.referencedLayer()
            name_join_field = ref.resolveReferencedField(field.field)
            ctx = QgsExpressionContext()
            ctx.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(name_layer))
            expr = QgsExpression(f"""{name_join_field} in ({','.join(f"'{i}'" for i in geoids)})""")
            request = QgsFeatureRequest(expr, ctx)
            request.setSubsetOfAttributes([name_layer.fields().lookupField(name_join_field), field.nameField.index])
            request.setInvalidGeometryCheck(QgsFeatureRequest.InvalidGeometryCheck.GeometryNoCheck)
            fi: Iterator[QgsFeature] = name_layer.getFeatures(expr)
            attr_tuples: list[tuple[str, str]] = [feat.attributes() for feat in fi]
            dd = dict(attr_tuples)
            return pd.Series(dd["name"], index=dd[name_join_field], name="__name")

        return None

    def calcPlanMetrics(self, data: pd.DataFrame, cols: list[str]):
        total = len(self.geoFields) + 1
        if self.popField in cols:
            self.totalPop = data[self.popField].sum()
        else:
            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))
            agg = QgsAggregateCalculator(self.popLayer)
            totalPop, success = agg.calculate(QgsAggregateCalculator.Sum, self.popField, context)
            if success:
                self.totalPop = int(totalPop)

        self.splits = {}
        for field in self.geoFields:
            g = data[[field.fieldName] + cols].groupby([field.fieldName])
            splits_data = g.filter(lambda x: x[self.distField].nunique() > 1)

            splitpop = splits_data[[field.fieldName] + cols] \
                .groupby([field.fieldName, self.distField]) \
                .sum()

            names = self.getSplitNames(field, splitpop.index.get_level_values(0).unique())
            if names:
                splitpop = splitpop.join(names)
                splitpop = splitpop.sort_values(by="__name")
            else:
                splitpop = splitpop.sort_index()

            self.splits[field.fieldName] = splitpop
            self.updateProgress(total, len(self.splits), 40, 50)

        self.cutEdges = self.calcCutEdges(data, self.distField)
        self.updateProgress(total, total, 40, 50)

    def calcDistrictMetrics(self, data: gpd.GeoDataFrame):
        cea_crs = pyproj.CRS('+proj=cea')
        cea: gpd.GeoSeries = data.geometry.to_crs(cea_crs)
        area = cea.area
        data['polsbypopper'] = 4 * math.pi * area / (cea.length**2)
        data['reock'] = area / cea.minimum_bounding_circle().area
        data['convexhull'] = area / cea.convex_hull.area

    def run(self) -> bool:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements

        debug_thread()

        try:
            self.setProgress(0)
            assign = self.pd_read(self.geoPackagePath, self.assignLayer.featureCount(),
                                  prog_start=0, prog_stop=20, layer="assignments")
            assign.set_index(self.geoIdField, inplace=True)

            cols = [self.distField]
            if self.includeDemographics:
                popdf = self.loadPopData()
                assign: gpd.GeoDataFrame = assign.join(popdf)
                cols += [self.popField] + [f.fieldName for f in self.popFields] + [f.fieldName for f in self.dataFields]

            self.calcPlanMetrics(assign, cols)

            if self.includeGeometry:
                cols.append("geometry")
                if self.updateDistricts:
                    dists = self.updateDistricts
                    total = len(self.updateDistricts) + 1
                else:
                    total = self.numDistricts + 2
                    dists = range(total)
                rows = []
                for d in dists:
                    rows.append(assign.loc[assign[self.distField] == d, cols]
                                .dissolve(by=self.distField, aggfunc="sum"))
                    self.updateProgress(total, len(rows), 50, 100)

                data = pd.concat(rows)

                self.calcDistrictMetrics(data)
                self.data = data.to_wkt()
                self.updateProgress(total, total, 50, 100)
            else:
                assign.drop(columns="geometry", inplace=True)
                total = len(assign)
                self.data = assign[cols].groupby(by=self.distField).sum()
                self.updateProgress(total, total, 50, 100)

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
                ideal = round(self.totalPop / self.numSeats)
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

    def _updateDistLayer(self):
        if not self.distLayer:
            return

        fields = {
            "deviation": "deviation REAL DEFAULT 0",
            "pct_deviation": "pct_deviation REAL DEFAULT 0",
            "description": "description TEXT",
            "members": "members INTEGER DEFAULT 1"
        }
        update_fields = []
        for f in fields:
            if self.distLayer.fields().lookupField(f) == -1:
                update_fields.append(f)
        if update_fields:
            sql = ";".join(f"ALTER TABLE districts ADD COLUMN {fields[f]}" for f in update_fields)
            with spatialite_connect(self.geoPackagePath) as db:
                db.executescript(sql)

    def finished(self, result: bool):
        super().finished(result)

        if not result:
            return

        self._updateDistLayer()

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
