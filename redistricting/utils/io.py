"""QGIS Redistricting Plugin - pandas and geopandas i/o

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

import os
import pathlib
import tempfile
import zipfile
from collections.abc import Iterable
from numbers import Number

import geopandas as gpd
import pandas as pd
import psycopg2
from osgeo import gdal, ogr
from packaging.version import parse as parse_version
from shapely import wkb
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from .gpkg import spatialite_connect
from .misc import quote_list

if hasattr(pd.options.mode, "copy_on_write"):
    pd.options.mode.copy_on_write = "warn"

DEC2FLOAT = psycopg2.extensions.new_type(
    psycopg2.extensions.DECIMAL.values, "DEC2FLOAT", lambda value, curs: float(value) if value is not None else None
)

psycopg2.extensions.register_type(DEC2FLOAT)


def ogr_type_to_dtype(ogr_type):
    if ogr_type in (ogr.OFTString, ogr.OFTWideString):
        t = str
    elif ogr_type == ogr.OFTReal:
        t = float
    elif ogr_type in (ogr.OFTInteger, ogr.OFTInteger64):
        t = int
    else:
        t = object

    return t


def is_shapezip(path: pathlib.Path):
    with zipfile.ZipFile(path, "r") as z:
        for f in z.namelist():
            if f.endswith(".shp"):
                return True

    return False


try:
    # pylint: disable-next=unused-import
    import pyogrio  # type: ignore

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
                filename, bbox=bbox, mask=mask, skip_features=skip_features, max_features=max_features, **kwargs
            )

        gpd.read_file = read_file_pygrio

except ImportError:
    gpd_io_engine = "fiona"
    gpd_read_file = gpd.read_file

    HeaderSize = {0: 8, 1: 40, 2: 56, 3: 46, 4: 72}

    def _read_sqlite(path: pathlib.Path, bbox=None, mask=None, rows=None, **kwargs):  # noqa: PLR0915, PLR0912
        def sql_to_wkb(geom: bytes):
            if geom[:2] == b"GP":
                s = HeaderSize[geom[3] >> 1 & 0b111]
                ofs = slice(s, None)
            else:
                ofs = slice(38, -1)
            return wkb.loads(geom[ofs])

        table = kwargs["layer"]
        if not table.isidentifier():
            raise ValueError(f"Invalid table name: {table!r}")
        cols = kwargs.get("columns")
        if cols is not None and not isinstance(cols, Iterable):
            raise TypeError("Invalid value for columns")

        with spatialite_connect(path) as db:
            c = db.execute("SELECT name FROM sqlite_schema WHERE type = 'table'")
            c.row_factory = lambda cursor, row: row[0]
            l = c.fetchall()
            if "gpkg_geometry_columns" in l:
                fmt = "gpkg"
                geom_tbl = "gpkg_geometry_columns"
                tbl_col = "table_name"
                geom_col = "column_name"
                srsid_col = "srs_id"
            elif "geometry_columns" in l:
                fmt = "spatialite"
                geom_tbl = "geometry_columns"
                tbl_col = "f_table_name"
                geom_col = "f_geometry_column"
                srsid_col = "srid"
            else:
                fmt = None

            if fmt:
                table = kwargs["layer"]

                # pylint: disable-next=possibly-used-before-assignment
                c = db.execute(f"SELECT {geom_col}, {srsid_col} FROM {geom_tbl} WHERE {tbl_col} = ?", (table,))  # noqa: S608
                geometry_column, srs_id = c.fetchone()

                if cols is None:
                    cols = ["*"]  # doesn't work with mask
                else:
                    cols = [*quote_list(cols), geometry_column]

                sql = f"SELECT {','.join(cols)} FROM {table}"  # noqa: S608

                # NOTE: no support for GeoSeries or GeoDataFrame bbox constraints
                bbox_where = mask_where = ""
                if isinstance(mask, gpd.GeoDataFrame):
                    mask: gpd.GeoSeries = mask.geometry

                if isinstance(mask, gpd.GeoSeries):
                    if parse_version(gpd.__version__) >= parse_version("1.0"):
                        mask = mask.union_all()
                    else:
                        mask = mask.unary_union

                if isinstance(mask, dict):
                    mask = shape(mask)

                if isinstance(mask, BaseGeometry):
                    mask_where = f"ST_Intersects({geometry_column}, ST_GeomFromWKB(x'{wkb.dumps(mask, hex=True)}'))"
                    bbox = mask.bounds
                elif isinstance(mask, (gpd.GeoSeries, gpd.GeoDataFrame)):
                    if parse_version(gpd.__version__) >= parse_version("1.0"):
                        mask = mask.union_all()
                    else:
                        mask = mask.unary_union
                    mask_where = f"ST_Intersects({geometry_column}, ST_GeomFromWKB(x'{wkb.dumps(mask, hex=True)}'))"
                    bbox = mask.total_bounds.tolist()

                if isinstance(bbox, (gpd.GeoSeries, gpd.GeoDataFrame)):
                    bbox = bbox.total_bounds.tolist()
                elif isinstance(bbox, BaseGeometry):
                    bbox = bbox.bounds

                if isinstance(bbox, (list, tuple)):
                    if fmt == "gpkg":
                        idx = f"rtree_{table}_{geometry_column}"
                        c = db.execute(f"PRAGMA table_info({table})").fetchall()
                        for r in c:
                            if r[-1] == 1:
                                pkey = r[1]
                                break
                        else:
                            pkey = None

                        idx_id = "id"
                    else:
                        pkey = "ROWID"
                        idx_id = "pkid"
                        idx = f"idx_{table}_{geometry_column}"

                    if pkey:
                        minx, miny, maxx, maxy = bbox
                        if (
                            not isinstance(minx, Number)
                            or not isinstance(miny, Number)
                            or not isinstance(maxx, Number)
                            or not isinstance(maxy, Number)
                        ):
                            raise ValueError("Invalid bbox")

                        bbox_where = (
                            f"{pkey} IN (SELECT {idx_id} FROM {idx} r "  # noqa: S608
                            f"WHERE r.minx < {maxx} and r.maxx >= {minx} "
                            f"AND r.miny < {maxy} and r.maxy >= {miny}"
                        )

                if mask_where and bbox_where:
                    where = f"{bbox_where} AND {mask_where}"
                else:
                    where = mask_where or bbox_where

                if where:
                    sql = f"{sql} WHERE {where}"

                if isinstance(rows, slice):
                    sql = f"{sql} LIMIT {rows.start}, {rows.stop - rows.start}"
                elif isinstance(rows, int):
                    sql = f"{sql} LIMIT {rows}"

                result = pd.read_sql(sql, db)
                result[geometry_column] = result[geometry_column].apply(sql_to_wkb)
                result = gpd.GeoDataFrame(result, geometry=geometry_column, crs=srs_id)
            else:
                # plain sqlite database
                if cols is None:
                    cols = ["*"]
                else:
                    cols = quote_list(cols)

                sql = f"SELECT {','.join(cols)} FROM {table}"  # noqa: S608
                result = pd.read_sql(sql, db)

        return result

    def read_file_no_fiona(filename, bbox=None, mask=None, rows=None, engine=None, **kwargs):
        if bbox is not None and mask is not None:
            raise ValueError("bbox and mask cannot both be provided")

        path = pathlib.Path(filename)
        if path.suffix in (".gpkg", ".sqlite", ".db") and "layer" in kwargs:
            return _read_sqlite(path, bbox, mask, rows, **kwargs)

        if path.suffix == ".zip" and is_shapezip(path):
            with tempfile.TemporaryDirectory() as d:
                with zipfile.ZipFile(path) as z:
                    z.extractall(d)
                return gpd_read_file(d, bbox, mask, rows, **kwargs)

        return gpd_read_file(filename, bbox, mask, rows, engine=engine, **kwargs)

    gpd.read_file = read_file_no_fiona

if parse_version(gdal.__version__) > parse_version("3.6"):
    try:
        # pylint: disable-next=unused-import
        import pyarrow  # type: ignore  # noqa

        os.environ["PYOGRIO_USE_ARROW"] = "1"
    except ImportError:
        pass
