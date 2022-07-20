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
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import math
from typing import Iterable, List, Set, Union, TYPE_CHECKING
from contextlib import closing
import pandas as pd
import geopandas as gpd
from shapely import wkt
from qgis.core import (
    QgsTask,
    QgsGeometry,
    QgsFeatureRequest,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsVectorLayer,
    QgsAggregateCalculator,
)
from qgis.utils import spatialite_connect
from ..Utils import tr
from ._exception import CancelledError
from ._debug import debug_thread

if TYPE_CHECKING:
    from .. import RedistrictingPlan, Field, DataField


class AggregateDistrictDataTask(QgsTask):
    """Task to aggregate the plan summary data and geometry in the background"""

    def __init__(
        self,
        plan: 'RedistrictingPlan',
        districts: Iterable[int] = None,
        includeDemographics=True,
        includeGeometry=True,
        useBuffer=True
    ):
        description = tr('Calculate district geometry and metrics')
        super().__init__(description, QgsTask.AllFlags)
        self.distList = plan.districts[:]
        self.assignLayer: QgsVectorLayer = plan.assignLayer
        self.distLayer: QgsVectorLayer = plan.distLayer
        self.popLayer: QgsVectorLayer = plan.popLayer
        self.distField: str = plan.distField
        self.geoIdField: str = plan.geoIdField
        self.joinField: str = plan.joinField
        self.popField: str = plan.popField
        self.vapField: str = plan.vapField
        self.cvapField: str = plan.cvapField
        self.dataFields: List['DataField'] = plan.dataFields
        self.geoFields: List['Field'] = plan.geoFields
        self.numDistricts: int = plan.numDistricts
        self.geoPackagePath = plan.geoPackagePath

        self.includeDistricts: Set[int] = None \
            if districts is None or set(districts) == set(range(0, self.numDistricts+1)) \
            else set(districts)

        self.includeGeometry = includeGeometry
        self.includeDemographics = includeDemographics
        self.useBuffer = useBuffer

        self.districts: Union[pd.DataFrame, gpd.GeoDataFrame] = None
        self.totalPop = 0
        self.cutEdges = []
        self.splits = {}
        self.calculateCutEdges = False
        self.calculateSplits = True
        self.exception = None

    def run(self) -> bool:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        def hasExpression():
            for f in self.dataFields:
                if f.isExpression:
                    return True

            return False

        def getData(data):
            nonlocal count

            if self.isCanceled():
                raise CancelledError()

            count += 1
            if count % 100 == 0:
                self.setProgress(98 * count/total)
            return data

        def getFieldValue(fld: 'DataField', context: QgsExpressionContext):
            return lambda f: fld.getValue(f, context)

        def addPopFields(cols: list, getters: list, context: QgsExpressionContext):
            cols.append(self.popField)
            getters.append(lambda f: f[self.popField])
            if self.vapField:
                cols.append(self.vapField)
                getters.append(lambda f: f[self.vapField])
            if self.cvapField:
                cols.append(self.cvapField)
                getters.append(lambda f: f[self.cvapField])
            cols.extend(
                fld.fieldName for fld in self.dataFields
            )
            getters.extend(
                getFieldValue(fld, context) for fld in self.dataFields
            )

        debug_thread()

        try:
            crs = self.assignLayer.crs()

            fields = self.assignLayer.fields()
            gIndex = fields.lookupField(self.geoIdField)
            dIndex = fields.lookupField(self.distField)
            cols = [self.geoIdField, self.distField]

            request = QgsFeatureRequest()
            if self.includeGeometry:
                cols.append('geometry')
            else:
                request.setFlags(QgsFeatureRequest.NoGeometry)

            if self.includeDistricts:
                context = QgsExpressionContext()
                context.appendScopes(
                    QgsExpressionContextUtils.globalProjectLayerScopes(self.assignLayer))
                request.setExpressionContext(context)

                flt = f"{self.distField} in ({','.join(str(d) for d in self.includeDistricts)})"  # pylint: disable=not-an-iterable
                if 0 in self.includeDistricts:  # pylint: disable=unsupported-membership-test
                    flt += f" or {self.distField} is null"
                request.setFilterExpression(flt)

                agg = QgsAggregateCalculator(self.assignLayer)
                agg.setFilter(flt)
                total, success = agg.calculate(QgsAggregateCalculator.Count, self.geoIdField, context)
                if not success:
                    total = 100
            else:
                total = self.assignLayer.featureCount()

            count = 0
            if self.includeDemographics:
                total *= 2

            request.setSubsetOfAttributes(cols, fields)

            if self.useBuffer:
                features = self.assignLayer.getFeatures(request)
            else:
                features = self.assignLayer.dataProvider().getFeatures(request)

            if self.includeGeometry:
                datagen = (getData([f[gIndex], f[dIndex], f.geometry().asWkt()]) for f in features)
            else:
                datagen = (getData([f[gIndex], f[dIndex]]) for f in features)
            df = pd.DataFrame.from_records(datagen, index=self.geoIdField, columns=cols)

            # convert null values to 0 if the "unassigned" district is among those being aggregated
            if not self.includeDistricts or 0 in self.includeDistricts:  # pylint: disable=unsupported-membership-test
                df[self.distField] = pd.to_numeric(df[self.distField], errors='coerce').fillna(0).astype(int)

            if self.includeDemographics:
                context = QgsExpressionContext()
                context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))

                cols = [self.joinField]
                getters = [lambda f: f[self.joinField]]
                addPopFields(cols, getters, context)

                request = QgsFeatureRequest()
                if self.includeDistricts is not None:
                    request.setExpressionContext(context)
                    r = ','.join([f"'{geoid}'" for geoid in df.index])
                    request.setFilterExpression(f'{self.joinField} in ({r})')

                if not hasExpression():
                    request.setSubsetOfAttributes(cols, self.popLayer.fields())

                features = self.popLayer.getFeatures(request)

                datagen = (getData([getter(f) for getter in getters]) for f in features)
                dfpop = pd.DataFrame.from_records(datagen, index=self.joinField, columns=cols)
                df = pd.merge(df, dfpop, how='left', left_index=True, right_index=True, copy=False)

            if self.includeGeometry:
                df['geometry'] = df.geometry.apply(wkt.loads)
                self.setProgress(99)

                gdf: gpd.GeoDataFrame = gpd.GeoDataFrame(
                    df, geometry='geometry', crs=crs.toWkt())

                self.districts: gpd.GeoDataFrame = gdf.dissolve(
                    by=self.distField, aggfunc='sum')
                self.setProgress(100)

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

                # calculate cut edges only if all districts are being aggregated
                if self.calculateCutEdges and self.includeDistricts is None:
                    try:
                        from redistricting.vendor.gerrychain import Graph, Partition, updaters  # pylint: disable=import-outside-toplevel

                        graph = Graph.from_geodataframe(gdf.to_crs('+proj=cea'), ignore_errors=True)
                        partition = Partition(
                            graph,
                            assignment=self.distField,
                            updaters={"cut_edges": updaters.cut_edges}
                        )
                        self.cutEdges = partition['cut_edges']
                    except ImportError:
                        self.cutEdges = []
                else:
                    self.cutEdges = []
            else:
                self.districts = df.groupby(by=self.distField).sum()
                self.cutEdges = []

            # calculate total population only if all districts are being aggregated
            if self.includeDemographics and self.includeDistricts is None:
                self.totalPop = int(self.districts[self.popField].sum())

            self.splits = {}
            if self.calculateSplits:
                with closing(spatialite_connect(self.geoPackagePath)) as db:
                    for field in self.geoFields:
                        sql = f'SELECT {field.fieldName}, COUNT(DISTINCT {self.distField}) AS splits ' \
                            f'FROM assignments GROUP BY {field.fieldName} HAVING splits > 1'
                        s = db.execute(sql).fetchall()
                        self.splits[field.fieldName] = s

        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

        return True

    def finished(self, result: bool):
        if not result:
            return

        name = [self.distList[d].name if d in self.distList else str(d) for d in self.districts.index]
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
