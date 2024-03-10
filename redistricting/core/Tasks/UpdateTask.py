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

import re
import shlex
from collections.abc import Iterator
from typing import (
    TYPE_CHECKING,
    Optional,
    Sequence,
    Union
)
from urllib.parse import (
    parse_qs,
    urlsplit
)

import geopandas as gpd
import pandas as pd
from qgis.core import (
    Qgis,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFeatureRequest,
    QgsMessageLog,
    QgsTask,
    QgsVectorLayer
)
from shapely import wkb

from ..Exception import CanceledError
from ..utils import gpd_io_engine
from .Sql import SqlAccess

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

    def checkCanceled(self):
        if self.isCanceled():
            raise CanceledError()

    def setProgressIncrement(self, start: int, stop: int):
        self.setProgress(start)
        self._prog_start = start
        self._prog_stop = stop

    def updateProgress(self, total, count):
        if total != 0:
            self.setProgress(min(100, self._prog_start + (self._prog_stop-self._prog_start)*count/total))

    def iterateWithProgress(self, it: Iterator, total: int = 0):
        count = 0
        for n in it:
            if total:
                count += 1
                self.updateProgress(total, count)
            self.checkCanceled()
            yield n

    def gpd_read(self, source, fc: int = 0, chunksize: Optional[int] = None, **kwargs):
        df: gpd.GeoDataFrame = None
        if (fc or chunksize):
            if chunksize is None:
                divisions = 10
                chunksize = fc // divisions
                lastchunk = fc % divisions
            elif fc > chunksize:
                divisions = fc // chunksize
                lastchunk = fc % chunksize
            else:
                divisions = 10
                lastchunk = 0

            chunks = [slice(n * chunksize, (n+1) * chunksize) for n in range(divisions)]
            if lastchunk:
                chunks += [slice(fc-lastchunk, fc)]

            df = pd.concat(
                self.iterateWithProgress((gpd.read_file(source, rows=s, **kwargs) for s in chunks), len(chunks))
            )
        else:
            df = gpd.read_file(source, **kwargs)
            self.updateProgress(len(df), len(df))
            self.checkCanceled()

        return df

    def read_qgis(
        self,
        layer: QgsVectorLayer,
        columns: Optional[list[str]] = None,
        order: Optional[str] = None,
        read_geometry=True,
        chunksize: Optional[int] = None,
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        def prog_attributes(f: QgsFeature):
            nonlocal count
            count += 1
            if count % chunksize == 0:
                self.checkCanceled()
                self.updateProgress(fc, count)
            attrs = [f.attribute(i) for i in indices]
            if read_geometry:
                attrs.append(f.geometry().asWkb().data())
            return attrs

        if not chunksize:
            chunksize = 1
        fc = layer.featureCount()
        count = 0
        fields = layer.fields()
        if columns is None:
            columns = fields.names()
            gen = (prog_attributes(f) for f in layer.getFeatures())
        else:
            indices = [fields.lookupField(c) for c in columns]
            if any((i == -1 for i in indices)):
                raise RuntimeError("Bad fields")
            req = QgsFeatureRequest()
            req.setSubsetOfAttributes(indices)
            gen = (prog_attributes(f) for f in layer.getFeatures(req))

        if read_geometry:
            columns = [*columns, "geometry"]
            df = pd.DataFrame(gen, columns=columns)
            df['geometry'] = df['geometry'].apply(wkb.loads)
            df = gpd.GeoDataFrame(df, geometry="geometry", crs=layer.crs().authid())
        else:
            df = pd.DataFrame(gen, columns=columns)

        if order and order in df.columns:
            df = df.sort_values(order).set_index(order)

        return df

    def read_layer(
            self,
            layer: QgsVectorLayer,
            columns: Optional[list[str]] = None,
            order: Optional[str] = None,
            read_geometry=True,
            chunksize: int = 0,
            use_qgis=False
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        def makeSqlQuery():
            if columns is None:
                cols = "*"
            else:
                cols = ",".join(columns)
                if read_geometry and (g := self.getGeometryColumn(layer)):
                    cols += f",{g}"
            sql = f"SELECT {cols} from {self.getTableName(layer)}"
            if order:
                sql = f"{sql} ORDER BY {order}"
            return sql

        fc = layer.featureCount()
        if chunksize <= 0:
            chunksize = None

        if fc != -1:
            if not chunksize:
                chunksize = fc // 10 if fc % 10 == 0 else fc // 9
                total = 10
            else:
                total = fc // chunksize + int(bool(fc % chunksize))
        else:
            total = 0

        if use_qgis or (gpd_io_engine == "fiona" and layer.storageType() == "ESRI Shapefile"):
            return self.read_qgis(layer, columns, order, read_geometry, chunksize)

        if layer.storageType() in ("GPKG", "OpenFileGDB"):
            if read_geometry:
                database, params = layer.dataProvider().dataSourceUri().split('|', 1)
                lexer = shlex.shlex(params)
                lexer.whitespace_split = True
                lexer.whitespace = '&'
                params = dict(pair.split('=', 1) for pair in lexer)
                df = self.gpd_read(database, layer.featureCount(), chunksize,
                                   layer=params['layername'], columns=columns)
                if order:
                    df = df.set_index(order).sort_index()
            else:
                with self._connectSqlOgrSqlite(layer.dataProvider()) as db:
                    df = pd.read_sql(makeSqlQuery(), db, index_col=order, columns=columns, chunksize=chunksize)
                if isinstance(df, Iterator):
                    df = pd.concat(self.iterateWithProgress(df, total))
        elif layer.dataProvider().name() in ('spatialite', 'SQLite'):
            if read_geometry:
                params = dict(
                    pair.split('=', 1) for pair in
                    shlex.split(re.sub(r' \(\w+\)', '', layer.dataProvider().dataSourceUri(True)))
                )
                df = self.gpd_read(params['dbname'], layer.featureCount(),
                                   chunksize, layer=params['table'], columns=columns)
                if order:
                    df = df.set_index(order).sort_index()
            else:
                with self._connectSqlNativeSqlite(layer.dataProvider()) as db:
                    df = pd.read_sql(makeSqlQuery(), db, index_col=order, columns=columns, chunksize=chunksize)
                if isinstance(df, Iterator):
                    df = pd.concat(self.iterateWithProgress(df, total))
        elif layer.dataProvider().name() in ('postgis', 'postgres'):
            with self._connectSqlPostgres(layer.dataProvider(), as_dict=False) as db:
                if read_geometry:
                    df = gpd.read_postgis(
                        makeSqlQuery(),
                        db,
                        self.getGeometryColumn(layer),
                        index_col=order,
                        chunksize=chunksize
                    )
                else:
                    df = pd.read_sql(
                        makeSqlQuery(),
                        db,
                        index_col=order,
                        columns=columns,
                        chunksize=chunksize
                    )

            if isinstance(df, Iterator):
                df = pd.concat(self.iterateWithProgress(df, total))
        elif layer.storageType() in ("ESRI Shapefile", "GeoJSON"):
            df = self.gpd_read(
                layer.source(),
                layer.featureCount(),
                columns=columns,
                chunksize=chunksize,
                read_geometry=read_geometry
            )
            if order:
                df = df.set_index(order).sort_index()
        elif layer.dataProvider().name() == "delimitedtext":
            uri_parts = urlsplit(layer.source())
            params = parse_qs(uri_parts.query)
            delimiter = params.get("delimiter", ",")[-1:]
            header = params.get("useHeader")
            if header is None:
                header = "infer"
            elif header in ("No", "False"):
                header = None
            else:
                header = 0

            if read_geometry:
                df = self.gpd_read(uri_parts.path, chunksize=chunksize, columns=columns)
            else:
                usecols = None if header is None else columns
                if chunksize is not None:
                    reader = pd.read_csv(
                        uri_parts.path,
                        delimiter=delimiter,
                        header=header,
                        usecols=usecols,
                        chunksize=chunksize
                    )
                    df = pd.concat(self.iterateWithProgress(reader.get_chunk(), total))
                else:
                    df = pd.read_csv(uri_parts.path, delimiter=delimiter, header=header, usecols=usecols)
                if header is None:
                    if len(columns) == len(df.columns):
                        df.columns = columns
        else:
            df = self.read_qgis(layer, columns, order, read_geometry, chunksize)

        self.checkCanceled()
        return df

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
                df[f.fieldName] = df.query(f.field)
        for f in self.dataFields:
            if f.isExpression:
                df[f.fieldName] = df.query(f.field)

        return df

    def finished(self, result: bool):
        super().finished(result)
        if not result:
            if self.exception is not None:
                QgsMessageLog.logMessage(
                    f'{self.exception!r}', 'Redistricting', Qgis.Critical)
