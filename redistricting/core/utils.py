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
import pathlib
from random import choice

import sqlite3

import re
from typing import TYPE_CHECKING, List, Union, Type
from processing.algs.gdal.GdalUtils import GdalUtils
from osgeo import gdal

from qgis.core import QgsVectorLayer, QgsDataSourceUri, QgsMessageLog
from qgis.PyQt.QtCore import QCoreApplication, QUrl
from qgis.PyQt.QtGui import QDesktopServices

if TYPE_CHECKING:
    from . import Field


# this file is part of qgis/QGIS-Mac-Packager package
# https://github.com/qgis/QGIS-Mac-Packager/issues/79


def tr(context, message=None):
    """Get the translation for a string using Qt translation API.

            :param message: String for translation.
            :type message: str, QString

            :returns: Translated version of message.
            :rtype: QString
            """
    if message is None:
        message = context
        context = 'Redistricting'
    return QCoreApplication.translate(context, message)


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
PRAGMA foreign_keys=OFF;

CREATE TABLE gpkg_spatial_ref_sys (
    srs_name                 TEXT    NOT NULL,
    srs_id                   INTEGER NOT NULL PRIMARY KEY,
    organization             TEXT    NOT NULL,
    organization_coordsys_id INTEGER NOT NULL,
    definition               TEXT    NOT NULL,
    description              TEXT
);

INSERT INTO gpkg_spatial_ref_sys VALUES (
    'Undefined cartesian SRS',
    -1,
    'NONE',
    -1,
    'undefined',
    'undefined cartesian coordinate reference system'
);

INSERT INTO gpkg_spatial_ref_sys VALUES (
    'Undefined geographic SRS',
    0,
    'NONE',
    0,
    'undefined',
    'undefined geographic coordinate reference system'
);

INSERT INTO gpkg_spatial_ref_sys VALUES (
    'WGS 84 geodetic',
    4326,
    'EPSG',
    4326,
    'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]',
    'longitude/latitude coordinates in decimal degrees on the WGS 84 spheroid'
);

CREATE TABLE gpkg_contents (
    table_name  TEXT     NOT NULL PRIMARY KEY,
    data_type   TEXT     NOT NULL,
    identifier  TEXT UNIQUE,
    description TEXT              DEFAULT '',
    last_change DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now')),
    min_x       DOUBLE,
    min_y       DOUBLE,
    max_x       DOUBLE,
    max_y       DOUBLE,
    srs_id      INTEGER,
    CONSTRAINT fk_gc_r_srs_id
        FOREIGN KEY (srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id)
);

CREATE TABLE gpkg_geometry_columns (
    table_name         TEXT    NOT NULL,
    column_name        TEXT    NOT NULL,
    geometry_type_name TEXT    NOT NULL,
    srs_id             INTEGER NOT NULL,
    z                  TINYINT NOT NULL,
    m                  TINYINT NOT NULL,
    CONSTRAINT pk_geom_cols PRIMARY KEY (table_name, column_name),
    CONSTRAINT uk_gc_table_name UNIQUE (table_name),
    CONSTRAINT fk_gc_tn FOREIGN KEY (table_name)
        REFERENCES gpkg_contents(table_name),
    CONSTRAINT fk_gc_srs FOREIGN KEY (srs_id)
        REFERENCES gpkg_spatial_ref_sys(srs_id)
);


CREATE TABLE gpkg_tile_matrix_set (
    table_name TEXT    NOT NULL PRIMARY KEY,
    srs_id     INTEGER NOT NULL,
    min_x      DOUBLE  NOT NULL,
    min_y      DOUBLE  NOT NULL,
    max_x      DOUBLE  NOT NULL,
    max_y      DOUBLE  NOT NULL,
    CONSTRAINT fk_gtms_table_name FOREIGN KEY (table_name)
        REFERENCES gpkg_contents(table_name),
    CONSTRAINT fk_gtms_srs FOREIGN KEY (srs_id)
        REFERENCES gpkg_spatial_ref_sys(srs_id)
);

CREATE TABLE gpkg_tile_matrix (
    table_name    TEXT    NOT NULL,
    zoom_level    INTEGER NOT NULL,
    matrix_width  INTEGER NOT NULL,
    matrix_height INTEGER NOT NULL,
    tile_width    INTEGER NOT NULL,
    tile_height   INTEGER NOT NULL,
    pixel_x_size  DOUBLE  NOT NULL,
    pixel_y_size  DOUBLE  NOT NULL,
    CONSTRAINT pk_ttm PRIMARY KEY (table_name, zoom_level),
    CONSTRAINT fk_tmm_table_name FOREIGN KEY (table_name)
        REFERENCES gpkg_contents(table_name)
);

CREATE TABLE gpkg_extensions (
    table_name     TEXT,
    column_name    TEXT,
    extension_name TEXT NOT NULL,
    definition     TEXT NOT NULL,
    scope          TEXT NOT NULL,
    CONSTRAINT ge_tce UNIQUE (table_name, column_name, extension_name)
);

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

        with spatialite_connect(gpkg) as db:
            db.executescript(CREATE_GPKG_SQL)
    except (sqlite3.Error, sqlite3.DatabaseError, sqlite3.OperationalError) as e:
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
            db.execute(CREATE_GPKG_OGR_CONTENTS_INSERT_TRIGGER_SQL.format(table=table))
            db.execute(CREATE_GPKG_OGR_CONTENTS_DELETE_TRIGGER_SQL.format(table=table))
    except (sqlite3.Error, sqlite3.DatabaseError, sqlite3.OperationalError):
        return False

    return True


DFLT_ALLOWED_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def random_id(length, allowed_chars=DFLT_ALLOWED_CHARS):
    return ''.join(choice(allowed_chars) for _ in range(length))
