# -*- coding: utf-8 -*-
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

import geopandas as gpd
import pandas as pd
import psycopg2
from osgeo import (
    gdal,
    ogr,
    osr
)
from packaging.version import parse as parse_version
from shapely import wkb

from .gpkg import spatialite_connect

pd.options.mode.copy_on_write = "warn"

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
                        sql = f"{sql} LIMIT {rows.start}, {rows.stop - rows.start}"
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
