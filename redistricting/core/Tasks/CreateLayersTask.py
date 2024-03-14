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

from ..Exception import CanceledError
from ..sql import SqlAccess
from ..utils import (
    createGeoPackage,
    createGpkgTable,
    spatialite_connect,
    tr
)
from ._debug import debug_thread

if TYPE_CHECKING:
    from .. import (
        DataField,
        Field,
        RedistrictingPlan
    )


class CreatePlanLayersTask(SqlAccess, QgsTask):
    def __init__(self, plan: RedistrictingPlan, gpkgPath, geoLayer: QgsVectorLayer, geoJoinField: str):
        super().__init__(tr('Create assignments layer'), QgsTask.AllFlags)
        self.path = gpkgPath

        self.assignFields = []
        self.numDistricts = plan.numDistricts

        self.geoLayer: QgsVectorLayer = geoLayer  # None
        self.geoField: QgsField = None
        self.geoJoinField = geoJoinField
        self.geoFields: List[Field] = list(plan.geoFields)

        authid = geoLayer.sourceCrs().authid()
        _, srid = authid.split(':', 1)
        self.srid = int(srid)

        self.popLayer: QgsVectorLayer = plan.popLayer
        self.popJoinField = plan.popJoinField
        self.popFields: List[Field] = list(plan.popFields)
        self.dataFields: List[DataField] = list(plan.dataFields)
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
            if not field.validate(popLayer):
                raise ValueError(field.error())
        for field in self.dataFields:
            if not field.validate(popLayer):
                raise ValueError(field.error())

    def getPopFieldTotalsAggregate(self, popLayer: QgsVectorLayer):
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))

        d = {self.distField: 0, 'name': 'Unassigned'}
        d[self.popField], _ = popLayer.aggregate(QgsAggregateCalculator.Sum, self.popField, context=context)
        for field in self.popFields:
            d[field.fieldName], _ = popLayer.aggregate(QgsAggregateCalculator.Sum, field.field, context=context)
        for field in self.dataFields:
            d[field.fieldName], _ = popLayer.aggregate(QgsAggregateCalculator.Sum, field.field, context=context)

        return d

    def makePopTotalsSqlSelect(self, table):
        sql = f'SELECT 0 as {self.distField}, \'{tr("Unassigned")}\' as name, SUM({self.popField}) as {self.popField}'

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
        sql = 'CREATE TABLE districts (' \
            'fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,' \
            f'{self.distField} INTEGER UNIQUE NOT NULL,' \
            'name TEXT DEFAULT \'\',' \
            'members INTEGER DEFAULT 1,' \
            f'{self.popField} REAL DEFAULT 0,' \
            'deviation REAL DEFAULT 0,' \
            'pct_deviation REAL DEFAULT 0,'

        fieldNames = {self.distField, 'name', 'members', self.popField, 'deviation', 'pct_deviation'}

        context = None
        for f in self.popFields:
            if f.fieldName in fieldNames:
                continue

            if f.isExpression and not context:
                context = QgsExpressionContext()
                context.appendScopes(
                    QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))
                context.setFeature(next(self.popLayer.getFeatures()))

            t = f.fieldType(context, self.popLayer)
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

            if f.isExpression and not context:
                context = QgsExpressionContext()
                context.appendScopes(
                    QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))
                context.setFeature(next(self.popLayer.getFeatures()))

            t = f.fieldType(context, self.popLayer)
            if t in (QVariant.Int, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong,
                     QVariant.Bool, QVariant.Date, QVariant.Time, QVariant.DateTime):
                tp = 'INTEGER'
            elif t == QVariant.Double:
                tp = 'REAL'
            else:
                continue

            sql += f'{f.fieldName} {tp},'
            fieldNames.add(f.fieldName)

        sql += 'polsbypopper REAL,' \
            'reock REAL,' \
            'convexhull REAL)'

        if createGpkgTable(self.path, 'districts', sql, srid=self.srid):
            with closing(spatialite_connect(self.path)) as db:
                db.execute(f'CREATE INDEX idx_districts_district ON districts ({self.distField})')

        return True

    def createDistricts(self):
        self.popTotals = self.getPopFieldTotals(self.popLayer)
        self.totalPop = self.popTotals[self.popField]

        with spatialite_connect(self.path) as db:
            sql = f"INSERT INTO districts ({self.distField}, name, {', '.join(self.popTotals)}) " \
                "VALUES (?,?,{','.join('?'*len(self.popTotals))})"
            db.execute(sql, [0, tr("Unassigned")] + list(self.popTotals.values()))
            sql = f"INSERT INTO districts ({self.distField}) VALUES (?)"
            db.executemany(sql, ((d+1,) for d in range(self.numDistricts)))

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

            t = f.fieldType(context, self.geoLayer)
            if t in (QVariant.Int, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong):
                tp = 'INTEGER'
            elif t in (QVariant.String, QVariant.ByteArray):
                tp = 'TEXT'
            else:
                continue

            sql += f',{f.fieldName} {tp}'
            fieldNames.append(f.fieldName)

        sql += ')'
        if createGpkgTable(self.path, 'assignments', sql, srid=self.srid):
            with closing(spatialite_connect(self.path)) as db:
                db.execute(f'CREATE INDEX idx_assignments_{self.distField} ON assignments ({self.distField})')
                for field in self.geoFields:
                    db.execute(f'CREATE INDEX idx_assignments_{field.fieldName} ON assignments ({field.fieldName})')
                db.commit()
        else:
            return False

        self.assignFields = fieldNames
        return True

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

            if self.createDistLayer():
                self.createDistricts()
                self.setProgress(2)
            else:
                return False

            if self.createAssignLayer():
                self.importSourceData()
            else:
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
