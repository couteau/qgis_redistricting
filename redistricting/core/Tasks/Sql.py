
# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - background task to create plan layers

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
import sqlite3
from typing import (
    Any,
    Dict,
    Iterable,
    Optional,
    Union
)
from urllib.parse import (
    parse_qs,
    urlsplit
)

import geopandas as gpd
import pandas as pd
import psycopg2
from osgeo import (
    gdal,
    ogr
)
from psycopg2.extras import RealDictConnection
from qgis.core import (
    QgsCredentials,
    QgsFeature,
    QgsFeatureRequest,
    QgsFeedback,
    QgsMapLayerUtils,
    QgsProject,
    QgsTask,
    QgsVectorDataProvider,
    QgsVectorLayer,
    QgsVirtualLayerDefinition
)
from shapely import wkb

from ..Exception import CancelledError
from ..utils import (
    gpd_io_engine,
    random_id,
    spatialite_connect
)


class SqlAccess:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._uri = None
        self._connInfo = None
        self._user = None
        self._passwd = None
        if isinstance(self, (QgsFeedback, QgsTask)):
            self._feedback = self
        elif "feedback" in kwargs and isinstance(kwargs["feedback"], (QgsFeedback, QgsTask)):
            self._feedback = kwargs["feedback"]
            del kwargs["feedback"]
        else:
            self._feedback = None

        self._prog_start = 0
        self._prog_stop = 100

    def setProgressIncrement(self, start: int, stop: int):
        self._feedback.setProgress(start)
        self._prog_start = start
        self._prog_stop = stop

    def updateProgress(self, total, count):
        if not self._feedback:
            return
        self._feedback.setProgress(min(100, self._prog_start + (self._prog_stop-self._prog_start)*count/total))
        if self._feedback.isCanceled():
            raise CancelledError()

    def gpd_read(self, source, fc=0, chunksize=None, **kwargs):
        df: gpd.GeoDataFrame = None
        if (fc or chunksize):
            if chunksize is None and fc != 0:
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
            for s in chunks:
                chunk = gpd.read_file(source, rows=s, **kwargs)
                if df is None:
                    df = chunk
                else:
                    df = pd.concat([df, chunk])
                self.updateProgress(fc, s.stop)
        else:
            df = gpd.read_file(source, **kwargs)
            self.updateProgress(len(df), len(df))

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
            chunksize: Optional[int] = None,
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

        if chunksize == 0:
            chunksize = None

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
                if chunksize is not None:
                    df = pd.concat(df)
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
                if chunksize is not None:
                    df = pd.concat(df)
        elif layer.dataProvider().name() in ('postgis', 'postgres'):
            with self._connectSqlPostgres(layer.dataProvider(), as_dict=False) as db:
                if read_geometry:
                    df = gpd.read_postgis(makeSqlQuery(), db, self.getGeometryColumn(layer),
                                          index_col=order, chunksize=chunksize)
                else:
                    df = pd.read_sql(makeSqlQuery(), db, self.getGeometryColumn(layer),
                                     index_col=order, columns=columns, chunksize=chunksize)
            if chunksize is not None:
                df = pd.concat(df)
        elif layer.storageType() in ("ESRI Shapefile", "GeoJSON"):
            df = self.gpd_read(layer.source(), layer.featureCount(), columns=columns,
                               chunksize=chunksize, read_geometry=read_geometry)
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
                    reader = pd.read_csv(uri_parts.path, delimiter=delimiter, header=header,
                                         usecols=usecols, chunksize=chunksize)
                    df = pd.concat(f for f in reader.get_chunk())
                else:
                    df = pd.read_csv(uri_parts.path, delimiter=delimiter, header=header, usecols=usecols)
                if header is None:
                    if len(columns) == len(df.columns):
                        df.columns = columns
        else:
            df = self.read_qgis(layer, columns, order, read_geometry, chunksize)

        return df

    def getTableName(self, layer: QgsVectorLayer):
        provider = layer.dataProvider()
        if provider.name() == 'ogr':
            if provider.storageType() in ('GPKG', 'SQLite'):
                _, params = provider.dataSourceUri().split('|', 1)
                lexer = shlex.shlex(params)
                lexer.whitespace_split = True
                lexer.whitespace = '&'
                params = dict(pair.split('=', 1) for pair in lexer)
                return params['layername']

            # for other drivers, get the name of the first layer from gdal
            # -- shoud work for single layer formats - shapefile and GeoJSON
            ds = gdal.OpenEx(provider.dataSourceUri(), gdal.OF_ALL)
            return ds.GetLayer().GetName()

        if provider.name() in ('spatialite', 'postgis', 'postgres'):
            params = dict(pair.split('=', 1) for pair in shlex.split(
                re.sub(r' \(\w+\)', '', provider.dataSourceUri(True))))
            return params['table']

        return None

    def getGeometryColumn(self, layer: QgsVectorLayer, table: str = None) -> str:
        if table is None:
            table = self.getTableName(layer)
        provider = layer.dataProvider()

        if provider.storageType() in ('GPKG', 'SQLite') or provider.name() in ('spatialite', 'postgis', 'postgres'):
            conn = QgsMapLayerUtils.databaseConnection(layer)
            if conn:
                if col := conn.table('', table).geometryColumn():
                    return col

        if provider.name() == 'ogr':
            database = provider.dataSourceUri().split('|')[0]
            ds: gdal.Dataset = gdal.OpenEx(database, gdal.OF_ALL)
            lyr: ogr.Layer = ds.GetLayerByName(table)
            col = lyr.GetGeometryColumn()

            # Shapefile and possibly other formats don't support
            # GetGeometryColumn, but GDAL provides no obvious way to directly
            # test whether the drivers support the GetGeometryColumn method -
            # use GetGeomType == wkbNone to test
            if not col and lyr.GetGeomType() not in (ogr.wkbUnknown, ogr.wkbNone):
                col = 'GEOMETRY'
            return col

        if provider.name() in ('spatialite', 'postgis', 'postgres'):
            if '.' in table:
                # remove the schema name and assume there's only one schema
                _, table = table.split('.', 1)
            r = self.executeSql(
                layer,
                f'select f_geometry_column from geometry_columns '
                f'where f_table_name=\'{table}\''
            )
            if r:
                return next(r)['f_geometry_column']

        return ''

    def _executeSqlSqlite(
        self, db: sqlite3.Connection, sql, as_dict
    ) -> Union[Iterable[Union[Iterable, sqlite3.Row]], None]:
        if as_dict:
            db.row_factory = sqlite3.Row
        cur = db.execute(sql)
        if cur.rowcount == 0:
            return None

        return cur

    def _connectSqlNativeSqlite(self, provider: QgsVectorDataProvider) -> sqlite3.Connection:
        conndata = dict(tuple(a.split('=')) for a in shlex.split(provider.uri().connectionInfo(True)))
        return spatialite_connect(conndata['dbname'])

    def _connectSqlOgrSqlite(self, provider: QgsVectorDataProvider) -> sqlite3.Connection:
        database, _ = provider.dataSourceUri().split('|', 1)
        return spatialite_connect(database)

    def _connectSqlPostgres(
        self, provider: QgsVectorDataProvider, as_dict: bool = True
    ) -> Union[RealDictConnection, psycopg2.extensions.connection]:
        if self._uri != provider.uri():
            self._uri = provider.uri()
            self._connInfo = self._uri.connectionInfo(True)
            connDict = dict(tuple(a.split('=')) for a in shlex.split(self._connInfo))
            self._user = connDict['user']
            self._passwd = connDict['password']
            if not self._user or not self._passwd:
                c = QgsCredentials.instance()
                c.lock()
                try:
                    (success, self._user, self._passwd) = c.get(self._connInfo, self._user, self._passwd)
                    if not success:
                        return None
                    self._uri.setUsername(self._user)
                    self._uri.setPassword(self._passwd)
                    self._connInfo = self._uri.connectionInfo(True)
                finally:
                    c.unlock()
        params = {'dsn': self._connInfo}
        if as_dict:
            params['connection_factory'] = RealDictConnection if as_dict else None
        return psycopg2.connect(**params)

    def _executeSqlNativeSqlite(self, provider: QgsVectorDataProvider, sql: str, as_dict: bool):
        with self._connectSqlNativeSqlite(provider) as db:
            return self._executeSqlSqlite(db, sql, as_dict)

    def _executeSqlOgrSqlite(self, provider: QgsVectorDataProvider, sql: str, as_dict: bool):
        with self._connectSqlOgrSqlite(provider) as db:
            return self._executeSqlSqlite(db, sql, as_dict)

    def _executeSqlPostgre(
        self, provider: QgsVectorDataProvider, sql: str, as_dict: bool
    ) -> Union[Iterable[Union[Iterable, Dict[str, Any]]], None]:
        with self._connectSqlPostgres(provider, as_dict) as db:
            cur = db.cursor()
            cur.execute(sql)
            if cur.rowcount == 0:
                return None

            return cur

    def createVirtualLayer(
        self,
        srcLayer: Union[QgsVectorLayer, Iterable[QgsVectorLayer]],
        sql: str,
        table=None
    ) -> QgsVectorLayer:
        try:
            iter(srcLayer)
        except TypeError:
            srcLayer = [srcLayer]

        # virtual layer only supports SELECT statements
        if not re.match(r'\s*select', sql, re.IGNORECASE):
            return None

        try:
            if table is None:
                if m := re.search(r'from\s+(?: \w +\.)?(\w+)', sql, re.IGNORECASE):
                    table = m.groups()[1]

            layers = []
            df = QgsVirtualLayerDefinition()
            for lyr in srcLayer:
                lyr = lyr.clone()

                QgsProject.instance().addMapLayer(lyr, False)
                layers.append(lyr)

                if table is None:
                    table = lyr.name()
                df.addSource(table, lyr.id())
                table = None

            df.setQuery(sql)

            return QgsVectorLayer(df.toString(), f'tmp_{random_id(6)}', 'virtual')
        finally:
            for lyr in layers:
                QgsProject.instance().removeMapLayer(lyr.id())

    def _executeSqlVirtualLayer(self, layer: QgsVectorLayer, sql: str,
                                as_dict: bool, table=None) -> Iterable[Dict[str, Any]]:
        # virtual layer only supports SELECT statements
        vl = self.createVirtualLayer(layer, sql, table)
        if as_dict:
            return (dict(zip(f.fields().names(), f.attributes())) for f in vl.getFeatures())

        return (f.attributes() for f in vl.getFeatures())

    def dbconnect(self, layer: QgsVectorLayer):
        provider = layer.dataProvider()
        if provider.name() == 'ogr' and provider.storageType() in ('GPKG', 'SQLite'):
            return self._connectSqlOgrSqlite(provider)
        elif provider.name() == 'spatialite':
            return self._connectSqlNativeSqlite(provider)
        elif provider.name() in ('postgis', 'postgres'):
            return self._connectSqlPostgres(provider)

        return None

    def executeSql(self, layer: QgsVectorLayer, sql: str, as_dict=True):
        provider = layer.dataProvider()
        if provider.name() == 'ogr' and provider.storageType() in ('GPKG', 'SQLite'):
            return self._executeSqlOgrSqlite(provider, sql, as_dict)
        elif provider.name() == 'spatialite':
            return self._executeSqlNativeSqlite(provider, sql, as_dict)
        elif provider.name() in ('postgis', 'postgres'):
            return self._executeSqlPostgre(provider, sql, as_dict)

        return self._executeSqlVirtualLayer(layer, sql, as_dict)

    def isSQLCapable(self, layer: QgsVectorLayer):
        provider = layer.dataProvider()
        if provider.name() == 'ogr':
            return provider.storageType() in ('GPKG', 'SQLite')

        return provider.name() in ('spatialite', 'postgis', 'postgres')
