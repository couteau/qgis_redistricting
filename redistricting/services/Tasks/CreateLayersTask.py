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
from __future__ import annotations

from contextlib import closing
from itertools import islice
from typing import (
    TYPE_CHECKING,
    List
)

from qgis.core import (
    Qgis,
    QgsAggregateCalculator,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsField,
    QgsMessageLog,
    QgsTask,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import QVariant

from ...exception import CanceledError
from ...models import (
    DistrictColumns,
    MetricsColumns
)
from ...utils import (
    SqlAccess,
    createGeoPackage,
    createGpkgTable,
    spatialite_connect,
    tr
)
from ._debug import debug_thread

if TYPE_CHECKING:
    from ...models import (
        RdsDataField,
        RdsField,
        RdsPlan
    )


class CreatePlanLayersTask(SqlAccess, QgsTask):
    def __init__(self, plan: RdsPlan, gpkgPath, geoLayer: QgsVectorLayer, geoJoinField: str):
        super().__init__(tr('Create assignments layer'), QgsTask.AllFlags)
        self.path = gpkgPath

        self.assignFields = []
        self.numDistricts = plan.numDistricts

        self.geoLayer: QgsVectorLayer = geoLayer  # None
        self.geoField: QgsField = None
        self.geoJoinField = geoJoinField
        self.geoFields: List[RdsField] = list(plan.geoFields)

        authid = geoLayer.sourceCrs().authid()
        _, srid = authid.split(':', 1)
        self.srid = int(srid)

        self.popLayer: QgsVectorLayer = plan.popLayer
        self.popJoinField = plan.popJoinField
        self.popFields: List[RdsField] = list(plan.popFields)
        self.dataFields: List[RdsDataField] = list(plan.dataFields)
        self.popField = plan.popField

        self.geoIdField = plan.geoIdField
        self.distField = plan.distField

        self.exception = None
        self.popTotals = {}
        self.totalPop = 0
        # self.getPopFieldTotals(plan.popLayer)
        self.setDependentLayers(l for l in (self.geoLayer, self.popLayer) if l is not None)

    def validatePopFields(self, popLayer: QgsVectorLayer):
        popFields = popLayer.fields()
        if popFields.lookupField(self.popJoinField) == -1:
            raise ValueError((f'Could not find field {self.popJoinField} in population layer'))
        if popFields.lookupField(self.popField) == -1:
            raise ValueError((f'Could not find field {self.popField} in population layer'))
        for field in self.popFields:
            if not field.validate():
                raise ValueError(*field.errors())
        for field in self.dataFields:
            if not field.validate():
                raise ValueError(*field.errors())

    def getPopFieldTotalsAggregate(self, popLayer: QgsVectorLayer):
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))

        d = {DistrictColumns.DISTRICT: 0, DistrictColumns.NAME: 'Unassigned'}
        d[DistrictColumns.POPULATION], _ = \
            popLayer.aggregate(QgsAggregateCalculator.Sum, self.popField, context=context)
        for field in self.popFields:
            d[field.fieldName], _ = popLayer.aggregate(QgsAggregateCalculator.Sum, field.field, context=context)
        for field in self.dataFields:
            d[field.fieldName], _ = popLayer.aggregate(QgsAggregateCalculator.Sum, field.field, context=context)

        return d

    def makePopTotalsSqlSelect(self, table):
        sql = f'SELECT 0 as {DistrictColumns.DISTRICT}, \'{tr("Unassigned")}\' as {DistrictColumns.NAME}, SUM({self.popField}) as {DistrictColumns.POPULATION}'

        for field in self.popFields:
            sql += f', SUM({field.field}) as {field.fieldName}'

        for field in self.dataFields:
            sql += f', SUM({field.field}) as {field.fieldName}'

        sql += f' FROM {table}'

        return sql

    def getPopFieldTotals(self, popLayer: QgsVectorLayer):

        if self.isSQLCapable(popLayer):
            table = self.getTableName(popLayer)
            if table:
                sql = self.makePopTotalsSqlSelect(table)
                r = self.executeSql(popLayer, sql)
                if r:
                    return dict(next(r))

        return self.getPopFieldTotalsAggregate(popLayer)

    def makeSourceLayers(self):
        self.geoField = self.geoLayer.fields().field(self.geoJoinField)
        if not self.geoField:
            raise ValueError(f'Source ID Field not found: {self.geoField}')

        self.validatePopFields(self.popLayer)

    def createDistLayer(self):
        fld = self.popLayer.fields()[self.popField]
        if fld.type() in (QVariant.Int, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong,
                          QVariant.Bool, QVariant.Date, QVariant.Time, QVariant.DateTime):
            poptype = 'INTEGER'
        elif fld.type() == QVariant.Double:
            poptype = 'REAL'
        else:
            raise ValueError(f'RdsField {self.popField} has invalid field type for population field')

        sql = 'CREATE TABLE districts (' \
            'fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,' \
            f'{DistrictColumns.DISTRICT} INTEGER UNIQUE NOT NULL,' \
            f'{DistrictColumns.NAME} TEXT DEFAULT \'\',' \
            f'{DistrictColumns.MEMBERS} INTEGER DEFAULT 1,' \
            f'{DistrictColumns.POPULATION} {poptype} DEFAULT 0,' \
            f'{DistrictColumns.DEVIATION} {poptype} DEFAULT 0,' \
            f'{DistrictColumns.PCT_DEVIATION} REAL DEFAULT 0,'

        fieldNames = {self.distField, 'name', 'members', self.popField, 'deviation', 'pct_deviation'}

        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))
        context.setFeature(next(self.popLayer.getFeatures()))
        for f in self.popFields:
            if f.fieldName in fieldNames:
                continue

            f.prepare(context)

            t = f.fieldType()
            if t in (QVariant.Int, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong,
                     QVariant.Bool, QVariant.Date, QVariant.Time, QVariant.DateTime):
                tp = 'INTEGER'
            elif t == QVariant.Double:
                tp = 'REAL'
            elif t in (QVariant.String, QVariant.ByteArray, QVariant.Char):
                tp = 'TEXT'
            else:
                continue

            sql += f'{f.fieldName} {tp},'
            fieldNames.add(f.fieldName)

        for f in self.dataFields:
            if f.fieldName in fieldNames:
                continue

            f.prepare(context)

            t = f.fieldType()
            if t in (QVariant.Int, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong,
                     QVariant.Bool, QVariant.Date, QVariant.Time, QVariant.DateTime):
                tp = 'INTEGER'
            elif t == QVariant.Double:
                tp = 'REAL'
            else:
                continue

            sql += f'{f.fieldName} {tp},'
            fieldNames.add(f.fieldName)

        sql += f'{MetricsColumns.POLSBYPOPPER} REAL,' \
            f'{MetricsColumns.REOCK} REAL,' \
            f'{MetricsColumns.CONVEXHULL} REAL)'

        success, error = createGpkgTable(self.path, 'districts', sql, srid=self.srid)
        if success:
            with closing(spatialite_connect(self.path)) as db:
                db.execute(f'CREATE INDEX idx_districts_district ON districts ({self.distField})')
        else:
            return False, error

        return True, None

    def createDistricts(self):
        self.popTotals = self.getPopFieldTotals(self.popLayer)
        self.totalPop = self.popTotals[DistrictColumns.POPULATION]

        with spatialite_connect(self.path) as db:
            sql = f"INSERT INTO districts ({', '.join(self.popTotals)}) VALUES ({','.join('?'*len(self.popTotals))})"
            db.execute(sql, list(self.popTotals.values()))
            # sql = f"INSERT INTO districts ({self.distField}) VALUES (?)"
            # db.executemany(sql, ((d+1,) for d in range(self.numDistricts)))

        return True

    def createAssignLayer(self):
        t = QgsField(self.geoField).type()
        if t in (QVariant.Int, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong):
            tp = 'INTEGER'
        elif t in (QVariant.String, QVariant.ByteArray):
            tp = 'TEXT'
        else:
            return False

        sql = 'CREATE TABLE assignments (' \
            'fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,' \
            f'{self.geoIdField} {tp} UNIQUE NOT NULL,' \
            f'{self.distField} INTEGER NOT NULL'

        fieldNames = [self.geoIdField, self.distField]

        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.geoLayer))
        context.setFeature(next(self.geoLayer.getFeatures()))
        for f in self.geoFields:
            if f.fieldName in fieldNames:
                continue

            f.prepare(context)
            t = f.fieldType()
            if t in (QVariant.Int, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong):
                tp = 'INTEGER'
            elif t in (QVariant.String, QVariant.ByteArray):
                tp = 'TEXT'
            else:
                continue

            sql += f',{f.fieldName} {tp}'
            fieldNames.append(f.fieldName)

        sql += ')'
        success, error = createGpkgTable(self.path, 'assignments', sql, srid=self.srid)
        if success:
            with closing(spatialite_connect(self.path)) as db:
                db.execute(f'CREATE INDEX idx_assignments_{self.distField} ON assignments ({self.distField})')
                for field in self.geoFields:
                    db.execute(f'CREATE INDEX idx_assignments_{field.fieldName} ON assignments ({field.fieldName})')
                db.commit()
        else:
            return False, error

        self.assignFields = fieldNames
        return True, None

    def importSourceData(self):
        total = self.geoLayer.featureCount()
        count = 0
        with spatialite_connect(self.path) as db:
            gen = None
            if self.isSQLCapable(self.geoLayer):
                table = self.getTableName(self.geoLayer)
                geocol = self.getGeometryColumn(self.geoLayer, table)
                if table and geocol:
                    sql = f'SELECT {self.geoJoinField}, 0 as district, '
                    for f in self.geoFields:
                        if f.fieldName in self.assignFields:
                            sql += f'{f.field} as {f.fieldName}, '
                    sql += f'ST_AsText({geocol}) as geometry FROM {table}'
                    gen = self.executeSql(self.geoLayer, sql, False)

            if not gen:
                context = QgsExpressionContext()
                context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.geoLayer))
                gen = (
                    [f[self.geoJoinField], 0] +
                    [field.getValue(f, context) for field in self.geoFields] +
                    [f.geometry().asWkt()]
                    for f in self.geoLayer.getFeatures()
                )

            sql = f'INSERT INTO assignments ({",".join(self.assignFields)}, geometry) ' \
                f'VALUES({",".join("?" * len(self.assignFields))}, GeomFromText(?))'
            chunkSize = max(1, total if total < 100 else total // 100)

            while count < total:
                s = islice(gen, chunkSize)
                if self.isCanceled():
                    raise CanceledError()
                db.executemany(sql, s)
                count = min(total, count + chunkSize)
                self.setProgress(2 + 97 * count/total)
            db.commit()
            db.execute(
                "UPDATE gpkg_ogr_contents SET feature_count = (SELECT COUNT(*) FROM assignments)"
            )

        return True

    def run(self):
        debug_thread()

        try:
            self.makeSourceLayers()
            self.setProgress(1)

            success, error = createGeoPackage(self.path)
            if not success:
                self.exception = error
                return False

            success, error = self.createDistLayer()
            if success:
                self.createDistricts()
                self.setProgress(2)
            else:
                self.exception = error
                return False

            success, error = self.createAssignLayer()
            if success:
                self.importSourceData()
            else:
                self.exception = error
                return False
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

    def finished(self, result: bool):
        if not result:
            if self.exception is not None:
                QgsMessageLog.logMessage(
                    f'{self.exception!r}', 'Redistricting', Qgis.Critical)
