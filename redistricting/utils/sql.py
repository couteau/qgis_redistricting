"""QGIS Redistricting Plugin - sql utilities and mixin

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Cryptodira
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
from typing import Any, Dict, Literal, Union, overload
from collections.abc import Iterable, Sequence

import psycopg2
from osgeo import gdal, ogr
from psycopg2.extensions import cursor
from psycopg2.extras import RealDictConnection
from qgis.core import (
    QgsCredentials,
    QgsFeature,
    QgsMapLayerUtils,
    QgsProject,
    QgsVectorDataProvider,
    QgsVectorLayer,
    QgsVirtualLayerDefinition,
)

from .gpkg import spatialite_connect
from .misc import random_id


class SqlAccess:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._uri = None
        self._connInfo = None
        self._user = None
        self._passwd = None

    def getTableName(self, layer: QgsVectorLayer):
        provider = layer.dataProvider()
        if provider.name() == "ogr":
            if provider.storageType() in ("GPKG", "SQLite"):
                uri_parts = provider.dataSourceUri().split("|")
                if len(uri_parts) <= 1:
                    raise ValueError("Could not determine table name from URI")
                lexer = shlex.shlex(uri_parts[1])
                lexer.whitespace_split = True
                lexer.whitespace = "&"
                params = dict(pair.split("=", 1) for pair in lexer)
                return params["layername"]

            # for other drivers, get the name of the first layer from gdal
            # -- shoud work for single layer formats - shapefile and GeoJSON
            ds = gdal.OpenEx(provider.dataSourceUri(), gdal.OF_ALL)
            return ds.GetLayer().GetName()

        if provider.name() in ("spatialite", "postgis", "postgres"):
            params = dict(
                pair.split("=", 1) for pair in shlex.split(re.sub(r" \(\w+\)", "", provider.dataSourceUri(True)))
            )
            return params["table"]

        return None

    def getGeometryColumn(self, layer: QgsVectorLayer, table: str = None) -> str:
        if table is None:
            table = self.getTableName(layer)
        provider = layer.dataProvider()

        if provider.storageType() in ("GPKG", "SQLite") or provider.name() in ("spatialite", "postgis", "postgres"):
            if "." in table:
                schema, table = table.split(".")
            else:
                schema = ""
            conn = QgsMapLayerUtils.databaseConnection(layer)
            if conn:
                if col := conn.table(schema, table).geometryColumn():
                    return col

        if provider.name() == "ogr":
            database = provider.dataSourceUri().split("|")[0]
            ds: gdal.Dataset = gdal.OpenEx(database, gdal.OF_ALL)
            lyr: ogr.Layer = ds.GetLayerByName(table)
            col = lyr.GetGeometryColumn()

            # Shapefile and possibly other formats don't support
            # GetGeometryColumn, but GDAL provides no obvious way to directly
            # test whether the drivers support the GetGeometryColumn method -
            # use GetGeomType == wkbNone to test
            if not col and lyr.GetGeomType() not in (ogr.wkbUnknown, ogr.wkbNone):
                col = "GEOMETRY"
            return col

        if provider.name() in ("spatialite", "postgis", "postgres"):
            if "." in table:
                # remove the schema name and assume there's only one schema
                _, table = table.split(".", 1)
            r = self.executeSql(
                layer,
                f"SELECT f_geometry_column FROM geometry_columns WHERE f_table_name='{table.replace("'", "''")}'",  # noqa: S608
            )
            if r:
                return next(r)["f_geometry_column"]

        return ""

    def _executeSqlSqlite(
        self, db: sqlite3.Connection, sql, parameters, *, as_dict: bool
    ) -> Union[Iterable[Union[Iterable, sqlite3.Row]], None]:
        if as_dict:
            db.row_factory = sqlite3.Row
        cur = db.execute(sql, parameters)
        if cur.rowcount == 0:
            return None

        return cur

    def _connectSqlNativeSqlite(self, provider: QgsVectorDataProvider) -> sqlite3.Connection:
        conndata = dict(tuple(a.split("=")) for a in shlex.split(provider.uri().connectionInfo(True)))
        return spatialite_connect(conndata["dbname"])

    def _connectSqlOgrSqlite(self, provider: QgsVectorDataProvider) -> sqlite3.Connection:
        database, _ = provider.dataSourceUri().split("|", 1)
        return spatialite_connect(database)

    def _connectSqlPostgres(
        self, provider: QgsVectorDataProvider, dict_connection: bool = True
    ) -> Union[RealDictConnection, psycopg2.extensions.connection]:
        if self._uri != provider.uri():
            self._uri = provider.uri()
            self._connInfo = self._uri.connectionInfo(True)
            connDict = dict(tuple(a.split("=")) for a in shlex.split(self._connInfo))
            self._user = connDict["user"]
            self._passwd = connDict["password"]
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
        params = {"dsn": self._connInfo}
        if dict_connection:
            params["connection_factory"] = RealDictConnection
        return psycopg2.connect(**params)

    def _executeSqlNativeSqlite(self, provider: QgsVectorDataProvider, sql: str, parameters, *, as_dict: bool):
        with self._connectSqlNativeSqlite(provider) as db:
            return self._executeSqlSqlite(db, sql, parameters, as_dict=as_dict)

    def _executeSqlOgrSqlite(self, provider: QgsVectorDataProvider, sql: str, parameters, *, as_dict: bool):
        with self._connectSqlOgrSqlite(provider) as db:
            return self._executeSqlSqlite(db, sql, parameters, as_dict=as_dict)

    def _executeSqlPostgre(
        self, provider: QgsVectorDataProvider, sql: str, parameters, *, as_dict: bool
    ) -> Union[Iterable[Union[Iterable, Dict[str, Any]]], None]:
        with self._connectSqlPostgres(provider, dict_connection=as_dict) as db:
            cur = db.cursor()
            cur.execute(sql, parameters)
            if cur.rowcount == 0:
                return None

            return cur

    def createVirtualLayer(
        self, srcLayer: Union[QgsVectorLayer, Iterable[QgsVectorLayer]], sql: str, table=None
    ) -> QgsVectorLayer:
        if isinstance(srcLayer, QgsVectorLayer):
            srcLayer = [srcLayer]

        # virtual layer only supports SELECT statements
        if not re.match(r"\s*select", sql, re.IGNORECASE):
            return None

        try:
            if table is None:
                if m := re.search(r"from\s+(?: \w +\.)?(\w+)", sql, re.IGNORECASE):
                    table = m.groups()[1]

            layers = []
            defn = QgsVirtualLayerDefinition()
            for lyr in srcLayer:
                lyr = lyr.clone()  # noqa: PLW2901

                QgsProject.instance().addMapLayer(lyr, False)
                layers.append(lyr)

                if table is None:
                    table = lyr.name()
                defn.addSource(table, lyr.id())
                table = None

            defn.setQuery(sql)

            return QgsVectorLayer(defn.toString(), f"tmp_{random_id(6)}", "virtual")
        finally:
            for lyr in layers:
                QgsProject.instance().removeMapLayer(lyr.id())

    def _executeSqlVirtualLayer(
        self, layer: QgsVectorLayer, sql: str, as_dict: bool, table=None
    ) -> Iterable[Union[dict[str, Any], QgsFeature]]:
        # virtual layer only supports SELECT statements
        vl = self.createVirtualLayer(layer, sql, table)
        if as_dict:
            return (dict(zip(f.fields().names(), f.attributes())) for f in vl.getFeatures())

        return (f.attributes() for f in vl.getFeatures())

    def dbconnect(self, layer: QgsVectorLayer):
        provider = layer.dataProvider()
        if provider.name() == "ogr" and provider.storageType() in ("GPKG", "SQLite"):
            return self._connectSqlOgrSqlite(provider)
        elif provider.name() == "spatialite":
            return self._connectSqlNativeSqlite(provider)
        elif provider.name() in ("postgis", "postgres"):
            return self._connectSqlPostgres(provider)

        return None

    @overload
    def executeSql(
        self, layer: QgsVectorLayer, sql: str, parameters=None, *, as_dict: Literal[True]
    ) -> Iterable[dict[str, Any]]: ...

    @overload
    def executeSql(
        self, layer: QgsVectorLayer, sql: str, parameters=None, *, as_dict: Literal[False]
    ) -> Union[cursor, Iterable[Sequence], Iterable[sqlite3.Row], Iterable[QgsFeature]]: ...

    def executeSql(self, layer: QgsVectorLayer, sql: str, parameters=None, *, as_dict=True):
        provider = layer.dataProvider()
        if provider.name() == "ogr" and provider.storageType() in ("GPKG", "SQLite"):
            return self._executeSqlOgrSqlite(provider, sql, parameters, as_dict=as_dict)
        elif provider.name() == "spatialite":
            return self._executeSqlNativeSqlite(provider, sql, parameters, as_dict=as_dict)
        elif provider.name() in ("postgis", "postgres"):
            return self._executeSqlPostgre(provider, sql, parameters, as_dict=as_dict)
        elif parameters is not None:
            raise ValueError(f"{provider.name()} does not support parameterized query")

        return self._executeSqlVirtualLayer(layer, sql, as_dict=as_dict)

    def isSQLCapable(self, layer: QgsVectorLayer):
        provider = layer.dataProvider()
        if provider.name() == "ogr":
            return provider.storageType() in ("GPKG", "SQLite")

        return provider.name() in ("spatialite", "postgis", "postgres")
