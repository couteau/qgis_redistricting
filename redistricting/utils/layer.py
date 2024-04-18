# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - layer utilities

        begin                : 2022-01-15
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
import re
import shlex
from typing import (
    Any,
    Iterator,
    Literal,
    Optional,
    Union,
    overload
)
from urllib.parse import (
    parse_qs,
    urlsplit
)

import geopandas as gpd
import pandas as pd
from qgis.core import (
    QgsFeature,
    QgsFeatureRequest,
    QgsFeedback,
    QgsVectorLayer
)
from shapely import wkb

from ..exception import CanceledError
from .intl import tr
from .io import gpd_io_engine
from .sql import SqlAccess


class LayerReader(SqlAccess):
    def __init__(self, layer: QgsVectorLayer, feedback: Optional[QgsFeedback] = None):
        super().__init__()
        if layer is None or not isinstance(layer, QgsVectorLayer):
            raise ValueError(tr("A QgsVectorLayer must be provided"))

        self._layer = layer
        self._feedback = feedback

    def updateProgress(self, total, count):
        if not self._feedback:
            return
        self._feedback.setProgress(min(100, 100 * count/total))
        if self._feedback.isCanceled():
            raise CanceledError()

    def checkCanceled(self):
        if self._feedback and self._feedback.isCanceled():
            raise CanceledError()

    def iterateWithProgress(self, it: Iterator, total: int = 0):
        count = 0
        for n in it:
            if total:
                count += 1
                self.updateProgress(total, count)
            else:
                self.checkCanceled()
            yield n

    def read_qgis(
        self,
        columns: Optional[list[str]] = None,
        order: Optional[str] = None,
        read_geometry=True,
        chunksize: Optional[int] = None,
        filt: Optional[dict[str, Any]] = None
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
        fc = self._layer.featureCount()
        count = 0
        fields = self._layer.fields()
        if columns is None:
            columns = fields.names()
            gen = (prog_attributes(f) for f in self._layer.getFeatures())
        else:
            indices = [fields.lookupField(c) for c in columns]
            if any((i == -1 for i in indices)):
                raise RuntimeError("Bad fields")
            req = QgsFeatureRequest()
            req.setSubsetOfAttributes(indices)
            if filt:
                filt = {f: f"{f'{v}' if isinstance(v, str) else v}" for f, v in filt.items()}
                expr = f"{'AND'.join(f'{f} = {v}' for f,v in filt.items())}"
                req.setFilterExpression(expr)
            gen = (prog_attributes(f) for f in self._layer.getFeatures(req))

        if read_geometry:
            columns = [*columns, "geometry"]
            df = pd.DataFrame(gen, columns=columns)
            df['geometry'] = df['geometry'].apply(wkb.loads)
            df = gpd.GeoDataFrame(df, geometry="geometry", crs=self._layer.crs().authid())
        else:
            df = pd.DataFrame(gen, columns=columns)

        if order and order in df.columns:
            df = df.sort_values(order).set_index(order)

        return df

    def gpd_read(
            self,
            source,
            fc: int = 0,
            chunksize: Optional[int] = None,
            filt: Optional[dict[str, Any]] = None,
            **kwargs
    ) -> gpd.GeoDataFrame:
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
            if filt:
                for f, v in filt.items():
                    df = df[df[f] == v]
        else:
            df = gpd.read_file(source, **kwargs)
            self.updateProgress(len(df), len(df))
            self.checkCanceled()

        return df

    @overload
    def read_layer(
        self,
        columns: Optional[list[str]] = ...,
        order: Optional[str] = ...,
        filt: Optional[dict[str, Any]] = ...,
        read_geometry: Literal[False] = ...,
        chunksize: int = ...
    ) -> pd.DataFrame:
        ...

    @overload
    def read_layer(
        self,
        columns: Optional[list[str]] = ...,
        order: Optional[str] = ...,
        filt: Optional[dict[str, Any]] = ...,
        read_geometry: Literal[True] = ...,
        chunksize: int = ...
    ) -> gpd.GeoDataFrame:
        ...

    def read_layer(
            self,
            columns=None,
            order=None,
            filt=None,
            read_geometry=True,
            chunksize=0
    ) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        def makeSqlQuery():
            nonlocal filt

            if columns is None:
                cols = "*"
            else:
                cols = ",".join(columns)
                if read_geometry and (g := self.getGeometryColumn(self._layer)):
                    cols += f",{g}"
            sql = f"SELECT {cols} from {self.getTableName(self._layer)}"
            if filt:
                filt = {f: f"{f'{v}' if isinstance(v, str) else v}" for f, v in filt.items()}
                sql = f"{sql} WHERE {' AND '.join(f'{f} = {v}' for f,v in filt.items())}"
            if order:
                sql = f"{sql} ORDER BY {order}"
            return sql

        fc = self._layer.featureCount()
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

        # use QGIS if reading a shapefile and the relevant engine is fiona -- otherwise, it crawls
        if gpd_io_engine == "fiona" and self._layer.storageType() == "ESRI Shapefile":
            return self.read_qgis(columns, order, read_geometry, chunksize, filt)

        if self._layer.storageType() in ("GPKG", "OpenFileGDB"):
            if read_geometry:
                database, params = self._layer.dataProvider().dataSourceUri().split('|', 1)
                lexer = shlex.shlex(params)
                lexer.whitespace_split = True
                lexer.whitespace = '&'
                params = dict(pair.split('=', 1) for pair in lexer)
                df = self.gpd_read(database, self._layer.featureCount(), chunksize,
                                   layer=params['layername'], columns=columns)
                if order:
                    df = df.set_index(order).sort_index()
            else:
                with self._connectSqlOgrSqlite(self._layer.dataProvider()) as db:
                    df = pd.read_sql(makeSqlQuery(), db, index_col=order, columns=columns, chunksize=chunksize)
                if isinstance(df, Iterator):
                    df = pd.concat(self.iterateWithProgress(df, total))
        elif self._layer.dataProvider().name() in ('spatialite', 'SQLite'):
            if read_geometry:
                params = dict(
                    pair.split('=', 1) for pair in
                    shlex.split(re.sub(r' \(\w+\)', '', self._layer.dataProvider().dataSourceUri(True)))
                )
                df = self.gpd_read(params['dbname'], self._layer.featureCount(),
                                   chunksize, layer=params['table'], columns=columns)
                if order:
                    df = df.set_index(order).sort_index()
            else:
                with self._connectSqlNativeSqlite(self._layer.dataProvider()) as db:
                    df = pd.read_sql(makeSqlQuery(), db, index_col=order, columns=columns, chunksize=chunksize)
                if isinstance(df, Iterator):
                    df = pd.concat(self.iterateWithProgress(df, total))
        elif self._layer.dataProvider().name() in ('postgis', 'postgres'):
            with self._connectSqlPostgres(self._layer.dataProvider(), as_dict=False) as db:
                if read_geometry:
                    df = gpd.read_postgis(
                        makeSqlQuery(),
                        db,
                        self.getGeometryColumn(self._layer),
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
        elif self._layer.storageType() in ("ESRI Shapefile", "GeoJSON"):
            df = self.gpd_read(
                self._layer.source(),
                self._layer.featureCount(),
                columns=columns,
                chunksize=chunksize,
                read_geometry=read_geometry
            )
            if order:
                df = df.set_index(order).sort_index()
        elif self._layer.dataProvider().name() == "delimitedtext":
            uri_parts = urlsplit(self._layer.source())
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
            df = self.read_qgis(self._layer, columns, order, read_geometry, chunksize)

        self.checkCanceled()
        return df
