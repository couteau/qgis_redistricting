"""QGIS Redistricting Plugin - GeoPackage utilities

        begin                : 2024-03-20
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

import pathlib
import re
import sqlite3
from contextlib import closing
from os import PathLike
from typing import Type, Union, overload

from osgeo import gdal
from processing.algs.gdal.GdalUtils import GdalUtils
from qgis.core import Qgis, QgsDataSourceUri, QgsMessageLog, QgsVectorLayer
from qgis.PyQt.QtCore import QCoreApplication


def getConnectionStringFromLayer(layer: QgsVectorLayer) -> str:
    if Qgis.versionInt() < 33801:
        return GdalUtils.ogrConnectionStringAndFormatFromLayer(layer)[0]  # pylint: disable=no-member
    else:
        return GdalUtils.gdal_connection_details_from_layer(layer).connection_string  # pylint: disable=no-member


def getOgrCompatibleSource(input_layer: QgsVectorLayer):
    ogr_data_path = None

    if input_layer is None or input_layer.dataProvider().name() == "memory":
        pass
    elif input_layer.dataProvider().name() == "ogr":
        ogr_data_path = getConnectionStringFromLayer(input_layer)
    elif input_layer.dataProvider().name() == "delimitedtext":
        ogr_data_path = getConnectionStringFromLayer(input_layer)[7:]
    elif input_layer.dataProvider().name().lower() == "wfs":
        uri = QgsDataSourceUri(input_layer.source())
        baseUrl = uri.param("url").split("?")[0]
        ogr_data_path = f"WFS:{baseUrl}"
    else:
        ogr_data_path = getConnectionStringFromLayer(input_layer)

    return ogr_data_path


def getTableName(layer: QgsVectorLayer, dataset: gdal.Dataset):
    if layer.dataProvider().name() == "ogr":
        table = GdalUtils.ogrLayerName(layer.dataProvider().dataSourceUri())
    elif dataset.GetLayerCount() == 1:
        table = dataset.GetLayer().GetName()
    else:
        table = layer.name()

    return table


def spatialite_connect(  # noqa: PLR0913
    database: Union[str, bytes, pathlib.Path],
    timeout: float = 5.0,
    detect_types: int = 0,
    isolation_level: str = "DEFERRED",
    check_same_thread: bool = True,
    factory: Type[sqlite3.Connection] = sqlite3.Connection,
    cached_statements: int = 128,
    uri: bool = False,
    enable_gpkg=None,
) -> sqlite3.Connection:
    """returns a dbapi2.Connection to a SpatiaLite db
    using the mod_spatialite_path() extension (python3)"""

    def fcnRegexp(pattern, string):
        result = re.search(pattern, string)
        return True if result else False

    con = sqlite3.connect(
        database,
        timeout=timeout,
        detect_types=detect_types,
        isolation_level=isolation_level,
        check_same_thread=check_same_thread,
        factory=factory,
        cached_statements=cached_statements,
        uri=uri,
    )
    con.enable_load_extension(True)
    cur = con.cursor()
    libs = [
        # SpatiaLite >= 4.2 and Sqlite >= 3.7.17, should work on all platforms
        ("mod_spatialite", "sqlite3_modspatialite_init"),
        # SpatiaLite >= 4.2 and Sqlite < 3.7.17 (Travis)
        ("mod_spatialite.so", "sqlite3_modspatialite_init"),
        # SpatiaLite < 4.2 (linux)
        ("libspatialite.so", "sqlite3_extension_init"),
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
    if enable_gpkg or (enable_gpkg is None and ".gpkg" in str(database)):
        try:
            cur.execute("SELECT EnableGpkgAmphibiousMode()")
        except (sqlite3.Error, sqlite3.DatabaseError, sqlite3.NotSupportedError):
            QgsMessageLog.logMessage(
                "warning:{}".format("Could not enable geopackage amphibious mode"),
                QCoreApplication.translate("Python", "Python warning"),
            )

    cur.close()
    con.enable_load_extension(False)
    con.create_function("regexp", 2, fcnRegexp)
    return con


# user_version 1.4
CREATE_GPKG_SQL = """
SELECT gpkgCreateBaseTables();
PRAGMA user_version=0x000028a0;
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
            pattern = gpkg.name + "*"
            for f in gpkg.parent.glob(pattern):
                f.unlink()

        with closing(spatialite_connect(gpkg, isolation_level="EXCLUSIVE")) as db:
            db.execute("BEGIN EXCLUSIVE")
            db.executescript(CREATE_GPKG_SQL)
    except (sqlite3.Error, sqlite3.DatabaseError, sqlite3.OperationalError) as e:
        return False, e

    return True, None


@overload
def createGpkgTable(
    gpkg: PathLike,
    table: str,
    create_table_sql: str,
    geom_column_name="geometry",
    geom_type="MULTIPOLYGON",
    srid=-1,
    create_spatial_index=True,
): ...


@overload
def createGpkgTable(
    db: sqlite3.Connection,
    table: str,
    create_table_sql: str,
    geom_column_name="geometry",
    geom_type="MULTIPOLYGON",
    srid=-1,
    create_spatial_index=True,
): ...


def createGpkgTable(  # noqa: PLR0913
    db,
    table: str,
    create_table_sql,
    geom_column_name="geometry",
    geom_type="MULTIPOLYGON",
    srid=-1,
    create_spatial_index=True,
):
    if not isinstance(srid, int):
        raise ValueError("Invalid srid passed to createGpkgTable")

    if not table.isidentifier():
        raise ValueError("Invalid table name passed to createGpkgTable")

    try:
        if not isinstance(db, sqlite3.Connection):
            db = spatialite_connect(db)

        db.execute(create_table_sql)
        if srid not in (-1, 0):
            if db.execute("SELECT count(*) FROM gpkg_spatial_ref_sys WHERE srs_id=?", (srid,)).fetchone()[0] == 0:
                db.execute(f"SELECT gpkgInsertEpsgSRID({srid})")
        db.execute(f'SELECT gpkgAddGeometryColumn("{table}", "{geom_column_name}" , "{geom_type}", 0 , 0, {srid} )')
        db.execute(f'SELECT gpkgAddGeometryTriggers("{table}", "{geom_column_name}")')
        if create_spatial_index:
            db.execute(f'SELECT gpkgAddSpatialIndex("{table}", "{geom_column_name}")')
        db.execute(CREATE_GPKG_OGR_CONTENTS_INSERT_TRIGGER_SQL.format(table=table))
        db.execute(CREATE_GPKG_OGR_CONTENTS_DELETE_TRIGGER_SQL.format(table=table))
    except (sqlite3.Error, sqlite3.DatabaseError, sqlite3.OperationalError) as e:
        return False, e

    return True, None


def connect_layer(layer: QgsVectorLayer) -> sqlite3.Connection:
    gpkg, _ = layer.source().split("|", 1)
    return spatialite_connect(gpkg)
