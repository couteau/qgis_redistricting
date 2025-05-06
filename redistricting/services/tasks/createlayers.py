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

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from contextlib import closing
from itertools import islice
from numbers import Integral, Real
from typing import TYPE_CHECKING, Any

import geopandas as gpd
from qgis.core import QgsExpressionContext, QgsExpressionContextUtils, QgsField, QgsVectorLayer
from qgis.PyQt.QtCore import QMetaType

from redistricting.models.field import RdsField

from ...errors import CanceledError
from ...models import DistrictColumns, MetricLevel
from ...utils import camel_to_snake, createGeoPackage, createGpkgTable, spatialite_connect, tr
from ..districtio import DistrictReader
from ._debug import debug_thread
from .updatebase import AggregateDataTask

if TYPE_CHECKING:
    from ...models import RdsPlan


class CreatePlanLayersTask(AggregateDataTask):
    def __init__(self, plan: RdsPlan, gpkgPath):
        super().__init__(plan, tr("Create assignments layer"))
        self.path = gpkgPath

        self.assignFields = []

        self.geoLayer: QgsVectorLayer = plan.geoLayer  # None
        self.geoJoinField = plan.geoJoinField
        self.geoField: QgsField = None

        authid = self.geoLayer.sourceCrs().authid()
        _, srid = authid.split(":", 1)
        self.srid = int(srid)

        self.popTotals = {}

        self.setDependentLayers(lyr for lyr in (self.geoLayer, self.popLayer) if lyr is not None)

    def sql_type(self, fld_type: QMetaType.Type) -> str:
        if fld_type in (
            QMetaType.Type.Int,
            QMetaType.Type.Short,
            QMetaType.Type.Long,
            QMetaType.Type.LongLong,
            QMetaType.Type.UInt,
            QMetaType.Type.UShort,
            QMetaType.Type.ULong,
            QMetaType.Type.ULongLong,
            QMetaType.Type.Bool,
            QMetaType.Type.QDate,
            QMetaType.Type.QTime,
            QMetaType.Type.QDateTime,
            QMetaType.Type.SChar,
            QMetaType.Type.UChar,
        ):
            t = "INTEGER"
        elif fld_type in (QMetaType.Type.Float, QMetaType.Type.Double):
            t = "REAL"
        elif fld_type in (
            QMetaType.Type.QString,
            QMetaType.Type.QByteArray,
            QMetaType.Type.QChar,
            QMetaType.Type.Char,
        ):
            t = "TEXT"
        else:
            t = "UNKNOWN"

        return t

    def validatePopFields(self, popLayer: QgsVectorLayer):
        popFields = popLayer.fields()
        if popFields.lookupField(self.popJoinField) == -1:
            raise ValueError((f"Could not find field {self.popJoinField} in population layer"))
        if popFields.lookupField(self.popField) == -1:
            raise ValueError((f"Could not find field {self.popField} in population layer"))
        for field in self.popFields:
            if not field.validate():
                raise ValueError(*field.errors())
        for field in self.dataFields:
            if not field.validate():
                raise ValueError(*field.errors())

    def validateSourceLayers(self):
        self.geoField = self.geoLayer.fields().field(self.geoJoinField)
        if not self.geoField:
            raise ValueError(f"Source ID Field not found: {self.geoField}")

        self.validatePopFields(self.popLayer)

    def getPopFieldTotals(self):
        return self.populationData.sum().to_dict()

    def createDistLayer(self, db: sqlite3.Connection):
        def addPopFields(flds: Iterable[RdsField]):
            for f in flds:
                if f.fieldName in fieldNames:
                    continue

                f.prepare(context)
                tp = self.sql_type(f.fieldType())
                if tp not in {"INTEGER", "REAL"}:
                    continue
                fields.append(f'"{f.fieldName}" {tp}')
                fieldNames.add(f.fieldName)

        poptype = self.sql_type(self.popLayer.fields()[self.popField].type())
        if poptype not in {"INTEGER", "REAL"}:
            raise ValueError(f"RdsField {self.popField} has invalid field type for population field")

        fields = [
            "fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            f"{DistrictColumns.DISTRICT} INTEGER UNIQUE NOT NULL",
            f"{DistrictColumns.NAME} TEXT DEFAULT ''",
            f"{DistrictColumns.MEMBERS} INTEGER DEFAULT 1",
            f"{DistrictColumns.POPULATION} {poptype} DEFAULT 0",
            f"{DistrictColumns.DEVIATION} {poptype} DEFAULT 0",
            f"{DistrictColumns.PCT_DEVIATION} REAL DEFAULT 0",
        ]

        fieldNames = {
            self.distField,
            DistrictColumns.NAME,
            DistrictColumns.MEMBERS,
            self.popField,
            DistrictColumns.DEVIATION,
            DistrictColumns.PCT_DEVIATION,
        }

        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))
        context.setFeature(next(self.popLayer.getFeatures()))

        addPopFields(self.popFields)
        addPopFields(self.dataFields)

        for m in self.plan.metrics.metrics:
            name = camel_to_snake(m.name())
            if name in fieldNames:
                continue

            if m.level() == MetricLevel.DISTRICT and m.serialize() and m.name() not in fieldNames:
                if issubclass(m.get_type(), Integral):
                    tp = "INTEGER"
                elif issubclass(m.get_type(), Real):
                    tp = "REAL"
                elif m.get_type() in (str, bytes):
                    tp = "TEXT"
                else:
                    continue

                fields.append(f"{name} {tp}")
                fieldNames.add(name)

        sql = f"CREATE TABLE districts (\n  {', '.join(fields)}\n)"

        success, error = createGpkgTable(db, "districts", sql, srid=self.srid)
        if success:
            db.execute(f"CREATE INDEX idx_districts_district ON districts ({self.distField})")
        else:
            return False, error

        return True, None

    def createDistricts(self, db: sqlite3.Connection):
        self.popTotals: dict[str, Any] = self.getPopFieldTotals()
        popFields = ", ".join(f'"{k}"' for k in self.popTotals)  # quote all field names
        self.totalPopulation = self.popTotals[DistrictColumns.POPULATION]
        sql = (
            f'INSERT INTO districts ("{self.distField}", {popFields}, geometry) '  # noqa: S608
            f"VALUES (0, {', '.join('?' * len(self.popTotals))}, (SELECT ST_union(geometry) FROM assignments))"
        )
        db.execute(sql, list(self.popTotals.values()))
        db.commit()

        return True

    def createAssignLayer(self, db: sqlite3.Connection):
        tp = self.sql_type(QgsField(self.geoField).type())
        if tp not in {"INTEGER", "TEXT"}:
            return False

        fields = [
            "fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            f"{self.geoIdField} {tp} UNIQUE NOT NULL",
            f"{self.distField} INTEGER NOT NULL DEFAULT 0",
        ]

        fieldNames = [self.geoIdField, self.distField]

        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.geoLayer))
        context.setFeature(next(self.geoLayer.getFeatures()))
        for f in self.geoFields:
            if f.fieldName in fieldNames:
                continue

            f.prepare(context)
            tp = self.sql_type(f.fieldType())
            if tp not in {"INTEGER", "TEXT"}:
                continue

            fields.append(f"{f.fieldName} {tp}")
            fieldNames.append(f.fieldName)

        sql = f"CREATE TABLE assignments ({','.join(fields)})"
        success, error = createGpkgTable(db, "assignments", sql, srid=self.srid)
        if success:
            db.execute(f"CREATE INDEX idx_assignments_{self.distField} ON assignments ({self.distField})")
            for field in self.geoFields:
                db.execute(f"CREATE INDEX idx_assignments_{field.fieldName} ON assignments ({field.fieldName})")
            db.commit()
        else:
            return False, error

        self.assignFields = fieldNames
        return True, None

    def importSourceData(self, db: sqlite3.Connection):
        total = self.geoLayer.featureCount()
        count = 0
        gen = None
        if self.isSQLCapable(self.geoLayer):
            table = self.getTableName(self.geoLayer)
            geocol = self.getGeometryColumn(self.geoLayer, table)
            if table and geocol:
                sql = f"SELECT {self.geoJoinField}, 0 as district, "
                for f in self.geoFields:
                    if f.fieldName in self.assignFields:
                        sql += f"{f.field} as {f.fieldName}, "
                sql += f"ST_AsText({geocol}) as geometry FROM {table}"
                if self.geoLayer.subsetString():
                    sql += f" WHERE {self.geoLayer.subsetString()}"
                gen = self.executeSql(self.geoLayer, sql, False)

        if not gen:
            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.geoLayer))
            gen = (
                [f[self.geoJoinField], 0]
                + [field.getValue(f, context) for field in self.geoFields]
                + [f.geometry().asWkt()]
                for f in self.geoLayer.getFeatures()
            )

        sql = (
            f"INSERT INTO assignments ({','.join(self.assignFields)}, geometry) "
            f"VALUES({','.join('?' * len(self.assignFields))}, GeomFromText(?))"
        )
        chunkSize = max(1, total if total < 100 else total // 100)

        while count < total:
            s = islice(gen, chunkSize)
            if self.isCanceled():
                raise CanceledError()
            db.executemany(sql, s)
            count = min(total, count + chunkSize)
            self.setProgress(2 + 97 * count / total)
        db.commit()
        db.execute("UPDATE gpkg_ogr_contents SET feature_count = (SELECT COUNT(*) FROM assignments)")
        db.commit()

        return True

    def run(self):
        debug_thread()

        try:
            self.validateSourceLayers()
            self.setProgress(1)

            self.populationData = self.loadPopData()

            success, error = createGeoPackage(self.path)
            if not success:
                self.exception = error
                return False

            with closing(spatialite_connect(self.path)) as db:
                success, error = self.createDistLayer(db)
                if not success:
                    self.exception = error
                    return False
                self.setProgress(2)

                success, error = self.createAssignLayer(db)
                if success:
                    self.importSourceData(db)
                else:
                    self.exception = error
                    return False

                self.createDistricts(db)

            self.populationData[self.distField] = 0  # add assignments column
            self.geometry = gpd.read_file(self.path, layer="districts").geometry
        except CanceledError:
            return False
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False
        finally:
            self.popLayer = None
            self.geoLayer = None

            self.setProgress(100)

        return True

    def finished(self, result):
        super().finished(result)
        self.plan.addLayersFromGeoPackage(self.path)
        reader = DistrictReader(self.plan.distLayer)
        unassigned = reader.readFromLayer()[0]
        self.plan.districts[0].update(unassigned)
