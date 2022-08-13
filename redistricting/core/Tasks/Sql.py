
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
from typing import Any, Dict, Iterable, Union
import psycopg2
from psycopg2.extras import RealDictConnection
from osgeo import gdal, ogr

from qgis.core import (
    QgsProject,
    QgsVectorDataProvider,
    QgsVectorLayer,
    QgsVirtualLayerDefinition,
)

from ..utils import spatialite_connect


class SqlAccess:
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
                provider.dataSourceUri(True).replace(' (geometry)', '')))
            return params['table']

        return None

    def getGeometryColumn(self, layer: QgsVectorLayer, table: str = None):
        if table is None:
            table = self.getTableName(layer)
        provider = layer.dataProvider()

        if provider.name() == 'ogr':
            # for other drivers, get the name of the first layer from gdal
            database, _ = provider.dataSourceUri().split('|', 1)
            ds: gdal.Dataset = gdal.OpenEx(database, gdal.OF_ALL)
            lyr: ogr.Layer = ds.GetLayerByName(table)
            return lyr.GetGeometryColumn()

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

        return None

    def _executeSqlSqlite(
        self, database, sql, as_dict
    ) -> Union[Iterable[Union[Iterable, sqlite3.Row]], None]:
        with spatialite_connect(database) as db:
            if as_dict:
                db.row_factory = sqlite3.Row
            cur = db.execute(sql)
            if cur.rowcount == 0:
                return None

            return cur

    def _executeSqlNativeSqlite(self, provider: QgsVectorDataProvider, sql: str, as_dict: bool):
        conndata = dict(tuple(a.split('=')) for a in shlex.split(
            provider.dataSourceUri(True).replace(' (geometry)', '')))
        return self._executeSqlSqlite(conndata['dbname'], sql, as_dict)

    def _executeSqlOgrSqlite(self, provider: QgsVectorDataProvider, sql: str, as_dict: bool):
        database, _ = provider.dataSourceUri().split('|', 1)
        return self._executeSqlSqlite(database, sql, as_dict)

    def _executeSqlPostgre(
        self, provider: QgsVectorDataProvider, sql: str, as_dict: bool
    ) -> Union[Iterable[Union[Iterable, Dict[str, Any]]], None]:
        conndata = dict(tuple(a.split('=')) for a in shlex.split(
            provider.dataSourceUri(True).replace(' (geometry', '')))

        conndata = {k: v for k, v in conndata.items() if k in ('dbname', 'host', 'port', 'sslmode', 'user', 'password')}

        params = {'dsn': ' '.join(['='.join(e) for e in zip(conndata.keys(), conndata.values())])}
        if as_dict:
            params['connection_factory'] = RealDictConnection if as_dict else None
        with psycopg2.connect(**params) as db:
            cur = db.cursor()
            cur.execute(sql)
            if cur.rowcount == 0:
                return None

            return cur

    def _executeSqlOgr(self, provider: QgsVectorDataProvider, sql: str, as_dict) -> Union[Iterable[Dict[str, Any]], None]:
        database, _ = provider.dataSourceUri().split('|')

        flags = gdal.OF_ALL
        if not re.match(r'\s*select', sql, re.I):
            flags |= gdal.OF_UPDATE

        ds: gdal.Dataset = gdal.OpenEx(database, flags)
        lyr: ogr.Layer = ds.ExecuteSQL(sql)
        if not lyr:
            return None

        if as_dict:
            if lyr.GetGeometryColumn():
                gen = (f.items() | {lyr.GetGeometryColumn(): f.geometry().ExportToWkt()} for f in lyr)
            else:
                gen = (f.items() for f in lyr)
        else:
            if lyr.GetGeometryColumn():
                gen = (list(f) + [f.geometry().ExportToWkt()] for f in lyr)
            else:
                gen = lyr

        return gen

    def _executeSqlVirtualLayer(self, layer: QgsVectorLayer, sql: str, as_dict: bool, table=None) -> Iterable[Dict[str, Any]]:
        # virtual layer only supports SELECT statements
        if not re.match(r'\s*select', sql, re.IGNORECASE):
            return None

        lyr = layer.clone()
        if table is None:
            if m := re.search(r'from\s+(?: \w +\.)?(\w+)', sql, re.IGNORECASE):
                table = m.groups()[0]
            else:
                table = layer.name()

        QgsProject.instance().addMapLayer(lyr, False)
        try:
            df = QgsVirtualLayerDefinition()
            df.addSource(table, lyr.id())
            df.setQuery(sql)

            vl = QgsVectorLayer(df.toString(), f'tmp_{lyr.id()}', "virtual")
            if as_dict:
                return (dict(zip(f.fields().names(), f.attributes())) for f in vl.getFeatures())

            return (f.attributes() for f in vl.getFeatures())
        finally:
            QgsProject.instance().removeMapLayer(lyr.id())

    def executeSql(self, layer: QgsVectorLayer, sql: str, as_dict=True):
        provider = layer.dataProvider()
        if provider.name() == 'ogr':
            if provider.storageType() in ('GPKG', 'SQLite'):
                return self._executeSqlOgrSqlite(provider, sql, as_dict)

            return self._executeSqlOgr(provider, sql, as_dict)
        elif provider.name() == 'spatialite':
            return self._executeSqlNativeSqlite(provider, sql, as_dict)
        elif provider.name() in ('postgis', 'postgres'):
            return self._executeSqlPostgre(provider, sql, as_dict)

        return self._executeSqlVirtualLayer(layer, sql, as_dict)

    def isSQLCapable(self, layer: QgsVectorLayer):
        provider = layer.dataProvider()
        return provider.name() in ('ogr', 'spatialite', 'postgis', 'postgres')
