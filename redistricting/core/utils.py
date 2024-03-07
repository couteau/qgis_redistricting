# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - utility functions

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
from __future__ import annotations

import os
import pathlib
import re
import sqlite3
from random import choice
from typing import (
    TYPE_CHECKING,
    List,
    Type,
    Union,
    overload
)

import geopandas as gpd
import pandas as pd
import psycopg2
from osgeo import (
    gdal,
    ogr,
    osr
)
from packaging.version import parse as parse_version
from processing.algs.gdal.GdalUtils import GdalUtils
from qgis.core import (
    QgsDataSourceUri,
    QgsMessageLog,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QUrl
)
from qgis.PyQt.QtGui import QDesktopServices
from shapely import wkb

DEC2FLOAT = psycopg2.extensions.new_type(
    psycopg2.extensions.DECIMAL.values,
    'DEC2FLOAT',
    lambda value, curs: float(value) if value is not None else None
)

psycopg2.extensions.register_type(DEC2FLOAT)

try:
    # pylint: disable-next=unused-import
    import pyogrio

    gpd_io_engine = "pyogrio"

    if parse_version(gpd.__version__) >= parse_version("0.11"):
        gpd.options.io_engine = "pyogrio"
    else:
        # if the installed geopandas doesn't support pyogrio, monkeypatch read_file
        gpd_read_file = gpd.read_file

        def read_file_pygrio(filename, bbox=None, mask=None, rows=None, engine=None, **kwargs):
            if engine is not None and engine != "pyogrio":
                return gpd_read_file(filename, bbox, mask, rows, **kwargs)

            if isinstance(rows, slice):
                skip_features = rows.start
                max_features = rows.stop - rows.start
            elif isinstance(rows, int):
                skip_features = 0
                max_features = rows
            else:
                skip_features = 0
                max_features = None

            return pyogrio.read_dataframe(
                filename, bbox=bbox, mask=mask,
                skip_features=skip_features, max_features=max_features,
                **kwargs
            )

        gpd.read_file = read_file_pygrio

except ImportError:
    gpd_io_engine = "fiona"
    gpd_read_file = gpd.read_file

    def read_file_no_fiona(filename, bbox=None, mask=None, rows=None, engine=None, **kwargs):
        path = pathlib.Path(filename)
        if path.suffix in ('.gpkg', '.sqlite', '.db') and "layer" in kwargs:
            with spatialite_connect(path) as db:
                table = kwargs["layer"]
                c = db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
                c.row_factory = lambda cursor, row: row[0]
                l = c.fetchall()
                if 'gpkg_geometry_columns' in l:
                    fmt = "gpkg"
                    geom_tbl = "gpkg_geometry_columns"
                    tbl_col = "table_name"
                    geom_col = "column_name"
                    srsid_col = "srs_id"
                elif 'geometry_columns' in l:
                    fmt = "spatialite"
                    geom_tbl = "geometry_columns"
                    tbl_col = "f_table_name"
                    geom_col = "f_geometry_column"
                    srsid_col = "srid"
                else:
                    fmt = None

                if fmt:
                    table = kwargs["layer"]

                    c = db.execute(f"SELECT {geom_col}, {srsid_col} FROM {geom_tbl} WHERE {tbl_col} = ?", (table,))
                    geometry_column, srs_id = c.fetchone()

                    cols = kwargs.get("columns")
                    if cols is None:
                        cols = ["*"]
                    else:
                        cols = [*cols, geometry_column]

                    sql = f"SELECT {','.join(cols)} FROM {table}"
                    if isinstance(rows, slice):
                        sql = f"{sql} OFFSET {rows.start} LIMIT {rows.stop - rows.start}"
                    elif isinstance(rows, int):
                        sql = f"{sql} LIMIT {rows}"

                    df = pd.read_sql(sql, db)
                    df[geometry_column] = df[geometry_column].apply(lambda x: wkb.loads(x[38:-1]))
                    df = gpd.GeoDataFrame(df, geometry=geometry_column, crs=srs_id)
                    return df

        if path.suffix == ".shp":
            ds: ogr.DataSource = ogr.Open(str(path))
            lyr: ogr.Layer = ds.GetLayer()
            crs: osr.SpatialReference = lyr.GetSpatialRef().GetAuthorityCode(None)
            ldef: ogr.FeatureDefn = lyr.GetLayerDefn()
            cols = kwargs.get("columns")
            if cols is None:
                cols = []
                for fi in range(ldef.GetFieldCount()):
                    fld: ogr.FieldDefn = ldef.GetFieldDefn(fi)
                    cols.append(fld.name)

            data = []
            index = []
            geom = []
            f: ogr.Feature
            if mask is not None and bbox is not None:
                raise ValueError()

            if bbox is not None:
                if isinstance(bbox, tuple):
                    lyr.SetSpatialFilterRect(*bbox)
                else:
                    lyr.SetSpatialFilter(bbox)

            if mask is not None:
                lyr.SetSpatialFilter(mask)

            if isinstance(rows, slice):
                lyr.SetNextByIndex(rows.start)
                count = rows.stop - rows.start
            elif isinstance(rows, int):
                count = rows
            else:
                count = -1
            for f in lyr:
                index.append(f.GetFID())
                data.append(tuple(f[c] for c in cols))
                geom.append(wkb.loads(bytes(f.geometry().ExportToWkb())))
                count -= 1
                if count == 0:
                    break

            df = pd.DataFrame.from_records(data, index=index, columns=cols)
            return gpd.GeoDataFrame(df, geometry=geom, crs=crs)

        return gpd_read_file(filename, bbox, mask, rows, engine, **kwargs)

    gpd.read_file = read_file_no_fiona

if parse_version(gdal.__version__) > parse_version("3.6"):
    try:
        # pylint: disable-next=unused-import
        import pyarrow
        os.environ["PYOGRIO_USE_ARROW"] = "1"
    except ImportError:
        pass


if TYPE_CHECKING:
    from . import Field


@overload
def tr(message: str):
    pass


@overload
def tr(context: str, message: str):
    pass


def tr(ctx_or_msg: str, message: str | None = None):
    """Get the translation for a string using Qt translation API.

            :param ctx_or_msg: Translation context or string for translation.
            :type message: str, QString

            :param message: String for translation.
            :type message: str, QString

            :returns: Translated version of message.
            :rtype: QString
            """
    if message is None:
        message = ctx_or_msg
        ctx_or_msg = 'redistricting'
    return QCoreApplication.translate(ctx_or_msg, message)


def makeFieldName(field: Field):
    if field.isExpression:
        name = (field.caption or field.field).lower()
        if not name.isidentifier():
            name = re.sub(r'[^\w]+', '_', name)
    else:
        name = field.field

    return name


def getDefaultField(layer: QgsVectorLayer, fieldList: List[Union[str, re.Pattern]]):
    for f in fieldList:
        if isinstance(f, str):
            if (i := layer.fields().lookupField(f)) != -1:
                return layer.fields()[i].name()
        elif isinstance(f, re.Pattern):
            for fld in layer.fields():
                if f.match(fld.name()):
                    return fld.name()

    return None


def matchField(field: str, layer: QgsVectorLayer, fieldList: List[Union[str, re.Pattern]]) -> bool:
    for f in fieldList:
        if isinstance(f, str):
            if field == f:
                return layer is None or layer.fields().lookupField(field) != -1
        elif isinstance(f, re.Pattern):
            if f.match(field):
                return layer is None or layer.fields().lookupField(field) != -1


def showHelp(helpPage='index.html'):
    """Display application help to the user."""
    helpfile = f'https://couteau.github.io/qgis_redistricting/{helpPage}'
    QDesktopServices.openUrl(QUrl(helpfile))


def getOgrCompatibleSource(input_layer: QgsVectorLayer):
    ogr_data_path = None

    if input_layer is None or input_layer.dataProvider().name() == 'memory':
        pass
    elif input_layer.dataProvider().name() == 'ogr':
        ogr_data_path = \
            GdalUtils.ogrConnectionStringAndFormatFromLayer(input_layer)[0]
    elif input_layer.dataProvider().name() == 'delimitedtext':
        ogr_data_path = GdalUtils.ogrConnectionStringFromLayer(
            input_layer)[7:]
    elif input_layer.dataProvider().name().lower() == 'wfs':
        uri = QgsDataSourceUri(input_layer.source())
        baseUrl = uri.param('url').split('?')[0]
        ogr_data_path = f"WFS:{baseUrl}"
    else:
        ogr_data_path = GdalUtils.ogrConnectionStringFromLayer(
            input_layer)

    return ogr_data_path


def getTableName(layer: QgsVectorLayer, dataset: gdal.Dataset):
    if layer.dataProvider().name() == 'ogr':
        table = GdalUtils.ogrLayerName(layer.dataProvider().dataSourceUri())
    elif dataset.GetLayerCount() == 1:
        table = dataset.GetLayer().GetName()
    else:
        table = layer.name()

    return table


def spatialite_connect(database: Union[str, bytes, pathlib.Path],
                       timeout: float = 5.0, detect_types: int = 0,
                       isolation_level: str = 'DEFERRED', check_same_thread: bool = True,
                       factory: Type[sqlite3.Connection] = sqlite3.Connection,
                       cached_statements: int = 128, uri: bool = False,
                       enable_gpkg=None) -> sqlite3.Connection:
    """returns a dbapi2.Connection to a SpatiaLite db
    using the mod_spatialite_path() extension (python3)"""

    def fcnRegexp(pattern, string):
        result = re.search(pattern, string)
        return True if result else False

    con = sqlite3.connect(
        database, timeout, detect_types, isolation_level,
        check_same_thread, factory, cached_statements, uri
    )
    con.enable_load_extension(True)
    cur = con.cursor()
    libs = [
        # SpatiaLite >= 4.2 and Sqlite >= 3.7.17, should work on all platforms
        ("mod_spatialite", "sqlite3_modspatialite_init"),
        # SpatiaLite >= 4.2 and Sqlite < 3.7.17 (Travis)
        ("mod_spatialite.so", "sqlite3_modspatialite_init"),
        # SpatiaLite < 4.2 (linux)
        ("libspatialite.so", "sqlite3_extension_init")
    ]
    found = False
    for lib, entry_point in libs:
        try:
            cur.execute(f"select load_extension('{lib}', '{entry_point}')")
        except sqlite3.OperationalError:
            continue
        else:
            found = True
            break
    if not found:
        raise RuntimeError("Cannot find any suitable spatialite module")
    if enable_gpkg or (enable_gpkg is None and '.gpkg' in str(database)):
        try:
            cur.execute("SELECT EnableGpkgAmphibiousMode()")
        except (sqlite3.Error, sqlite3.DatabaseError, sqlite3.NotSupportedError):
            QgsMessageLog.logMessage("warning:{}".format("Could not enable geopackage amphibious mode"),
                                     QCoreApplication.translate("Python", "Python warning"))

    cur.close()
    con.enable_load_extension(False)
    con.create_function("regexp", 2, fcnRegexp)
    return con


CREATE_GPKG_SQL = """
SELECT gpkgCreateBaseTables();
CREATE TABLE gpkg_ogr_contents (
    table_name    TEXT NOT NULL PRIMARY KEY,
    feature_count INTEGER DEFAULT NULL
);
"""

CREATE_GPKG_OGR_CONTENTS_INSERT_TRIGGER_SQL = """
    CREATE TRIGGER trigger_insert_feature_count_{table}
    AFTER INSERT ON {table}
    BEGIN UPDATE gpkg_ogr_contents SET feature_count = feature_count + 1 
          WHERE lower(table_name) = lower('{table}'); END;
"""


CREATE_GPKG_OGR_CONTENTS_DELETE_TRIGGER_SQL = """
    CREATE TRIGGER trigger_delete_feature_count_{table}
    AFTER DELETE ON {table}
    BEGIN UPDATE gpkg_ogr_contents SET feature_count = feature_count - 1 
          WHERE lower(table_name) = lower('{table}'); END;
"""


def createGeoPackage(gpkg):
    try:
        if isinstance(gpkg, str):
            gpkg = pathlib.Path(gpkg)

        if gpkg.exists():
            pattern = gpkg.name + '*'
            for f in gpkg.parent.glob(pattern):
                f.unlink()

        gdal.UseExceptions()
        drv: gdal.Driver = gdal.GetDriverByName("GPKG")
        ds: gdal.Dataset = drv.Create(
            str(gpkg), 0, 0, 0,
            options=["VERSION=1.4", "ADD_GPKG_OGR_CONTENTS=YES",
                     "METADATA_TABLES=YES", "DATETIME_FORMAT=UTC"]
        )
        ds.Close()
    except (PermissionError, RuntimeError) as e:
        return False, e

    return True, None


def createGpkgTable(gpkg, table, create_table_sql, geom_column_name='geometry',
                    geom_type='MULTIPOLYGON', srid=-1, create_spatial_index=True):
    try:
        with spatialite_connect(gpkg) as db:
            db.execute(create_table_sql)
            if srid not in (-1, 0):
                if db.execute(f'SELECT count(*) FROM gpkg_spatial_ref_sys WHERE srs_id={srid}').fetchone()[0] == 0:
                    db.execute(f'SELECT gpkgInsertEpsgSRID({srid})')
            db.execute(f'SELECT gpkgAddGeometryColumn("{table}", "{geom_column_name}" , "{geom_type}", 0 , 0, {srid} )')
            db.execute(f'SELECT gpkgAddGeometryTriggers("{table}", "{geom_column_name}")')
            if create_spatial_index:
                db.execute(f'SELECT gpkgAddSpatialIndex("{table}", "{geom_column_name}")')
            # db.execute(CREATE_GPKG_OGR_CONTENTS_INSERT_TRIGGER_SQL.format(table=table))
            # db.execute(CREATE_GPKG_OGR_CONTENTS_DELETE_TRIGGER_SQL.format(table=table))
    except (sqlite3.Error, sqlite3.DatabaseError, sqlite3.OperationalError):
        return False

    return True


DFLT_ALLOWED_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def connect_layer(layer: QgsVectorLayer) -> sqlite3.Connection:
    gpkg, _ = layer.source().split('|', 1)
    return spatialite_connect(gpkg)


def random_id(length, allowed_chars=DFLT_ALLOWED_CHARS):
    return ''.join(choice(allowed_chars) for _ in range(length))
