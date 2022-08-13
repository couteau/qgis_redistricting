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
from itertools import islice
from typing import List, TYPE_CHECKING
from contextlib import closing

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsAggregateCalculator,
    QgsMessageLog,
    QgsTask,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsField,
    QgsVectorLayer
)

from .Sql import SqlAccess
from ._exception import CancelledError
from ._debug import debug_thread
from ..utils import tr, spatialite_connect, createGeoPackage, createGpkgTable

if TYPE_CHECKING:
    from .. import RedistrictingPlan, Field, DataField


class CreatePlanLayersTask(SqlAccess, QgsTask):
    def __init__(self, plan: RedistrictingPlan, gpkgPath, srcLayer: QgsVectorLayer, srcGeoIdField: str):
        super().__init__(tr('Create assignments layer'), QgsTask.AllFlags)
        self.path = gpkgPath

        self.assignFields = []

        self.srcLayer: QgsVectorLayer = None
        self.srcField: QgsField = None
        self.srcGeoIdField = srcGeoIdField
        self.geoFields: List[Field] = list(plan.geoFields)
        self.srcUri = srcLayer.dataProvider().dataSourceUri(True)
        self.srcDrv = srcLayer.providerType()

        authid = srcLayer.sourceCrs().authid()
        _, srid = authid.split(':', 1)
        self.srid = int(srid)

        self.popLayer: QgsVectorLayer = None
        self.joinField = plan.joinField
        self.dataFields: List[DataField] = list(plan.dataFields)
        self.popField = plan.popField
        self.vapField = plan.vapField
        self.cvapField = plan.cvapField
        self.popUri = plan.popLayer.dataProvider().dataSourceUri(True)
        self.popDrv = plan.popLayer.providerType()

        self.geoIdField = plan.geoIdField
        self.distField = plan.distField

        self.exception = None
        self.popTotals = {}
        self.totalPop = 0
        # self.getPopFieldTotals(plan.popLayer)

    def validatePopFields(self, popLayer):
        popFields = popLayer.fields()
        if popFields.lookupField(self.joinField) == -1:
            raise ValueError((f'Could not find field {self.joinField} in population layer'))
        if popFields.lookupField(self.popField) == -1:
            raise ValueError((f'Could not find field {self.popField} in population layer'))
        if self.vapField and popFields.lookupField(self.vapField) == -1:
            raise ValueError((f'Could not find field {self.vapField} in population layer'))
        if self.cvapField and popFields.lookupField(self.cvapField) == -1:
            raise ValueError((f'Could not find field {self.cvapField} in population layer'))
        for field in self.dataFields:
            if not field.validate(popLayer):
                raise ValueError(field.error())

    def getPopFieldTotalsAggregate(self, popLayer: QgsVectorLayer):
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))

        d = {self.distField: 0, 'name': 'Unassigned'}
        d[self.popField], _ = popLayer.aggregate(QgsAggregateCalculator.Sum, self.popField, context=context)
        if self.vapField:
            d[self.vapField], _ = popLayer.aggregate(QgsAggregateCalculator.Sum, self.vapField, context=context)
        if self.cvapField:
            d[self.cvapField], _ = popLayer.aggregate(QgsAggregateCalculator.Sum, self.cvapField, context=context)
        for fld in self.dataFields:
            d[fld.fieldName], _ = popLayer.aggregate(QgsAggregateCalculator.Sum, fld.field, context=context)

        return d

    def makePopTotalsSqlSelect(self, table):
        sql = f'SELECT 0 as {self.distField}, \'{tr("Unassigned")}\' as name, SUM({self.popField}) as {self.popField}'

        if self.vapField:
            sql += f', SUM({self.vapField}) as {self.vapField}'
        if self.cvapField:
            sql += f', SUM({self.cvapField}) as {self.cvapField}'

        for f in self.dataFields:
            sql += f', SUM({f.field}) as {f.fieldName}'

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
        self.srcLayer = QgsVectorLayer(self.srcUri, '__redistricting__srclayer__', self.srcDrv)
        if not self.srcLayer.isValid():
            raise ValueError(f'Could not open source layer: {self.srcUri}')
        self.srcField = self.srcLayer.fields().field(self.srcGeoIdField)
        if not self.srcField:
            raise ValueError(f'Source ID Field not found: {self.srcField}')

        if self.popUri == self.srcUri:
            self.popLayer = self.srcLayer
        else:
            self.popLayer = QgsVectorLayer(self.popUri, '__redistricting__poplayer__', self.popDrv)
            if not self.popLayer.isValid():
                raise ValueError(f'Could not open population layer: {self.popUri}')

        self.validatePopFields(self.popLayer)

    def createDistLayer(self):
        sql = 'CREATE TABLE districts (' \
            'fid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,' \
            f'{self.distField} INTEGER UNIQUE NOT NULL,' \
            'name TEXT DEFAULT \'\',' \
            'members INTEGER DEFAULT 1,' \
            f'{self.popField} REAL DEFAULT 0,'

        fieldNames = {self.distField, 'name', 'members', self.popField}

        if self.vapField and self.vapField not in fieldNames:
            sql += f'{self.vapField} REAL DEFAULT 0,'
            fieldNames.add(self.vapField)
        if self.cvapField and self.cvapField not in fieldNames:
            sql += f'{self.cvapField} REAL DEFAULT 0,'
            fieldNames.add(self.cvapField)

        context = None
        for f in self.dataFields:
            if f.fieldName in fieldNames:
                continue

            if f.isExpression:
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

        sql += 'polsbypopper REAL,' \
            'reock REAL,' \
            'convexhull REAL)'

        return createGpkgTable(self.path, 'districts', sql, srid=self.srid)

    def createUnassigned(self):
        self.popTotals = self.getPopFieldTotals(self.popLayer)
        self.totalPop = self.popTotals[self.popField]

        l = QgsVectorLayer(f'{self.path}|layername=districts', '__districts', 'ogr')
        feat = QgsFeature(l.fields())
        for fld, value in self.popTotals.items():
            if l.fields().lookupField(fld) != -1:
                feat.setAttribute(fld, value)
        l.dataProvider().addFeature(feat)
        l.updateExtents()
        del l

        return True

    def createAssignLayer(self):
        t = QgsField(self.srcField).type()
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
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.srcLayer))
        context.setFeature(next(self.srcLayer.getFeatures()))
        for f in self.geoFields:
            if f.fieldName in fieldNames:
                continue

            t = f.fieldType(context, self.srcLayer)
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
        total = self.srcLayer.featureCount()
        count = 0
        with closing(spatialite_connect(self.path)) as db:
            gen = None
            if self.isSQLCapable(self.srcLayer):
                table = self.getTableName(self.srcLayer)
                geocol = self.getGeometryColumn(self.srcLayer, table)
                if table and geocol:
                    sql = f'SELECT {self.srcGeoIdField}, 0 as district, '
                    for f in self.geoFields:
                        if f.fieldName in self.assignFields:
                            sql += f'{f.field} as {f.fieldName}, '
                    sql += f'ST_AsText({geocol}) FROM {table}'
                    gen = self.executeSql(self.srcLayer, sql, False)

            if not gen:
                context = QgsExpressionContext()
                context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.srcLayer))
                gen = (
                    [f[self.srcGeoIdField], 0] +
                    [field.getValue(f, context) for field in self.geoFields] +
                    [f.geometry().asWkt()]
                    for f in self.srcLayer.getFeatures()
                )

            sql = f'INSERT INTO assignments ({",".join(self.assignFields)}, geometry) ' \
                f'VALUES({",".join("?" * len(self.assignFields))}, GeomFromText(?))'
            chunkSize = max(1, total if total < 100 else total // 100)
            while count < total:
                s = islice(gen, chunkSize)
                if self.isCanceled():
                    raise CancelledError()
                db.executemany(sql, s)
                count = min(total, count + chunkSize)
                self.setProgress(2 + 97 * count/total)
            db.commit()

        return True

    def run(self):
        debug_thread()

        try:
            self.makeSourceLayers()
            self.setProgress(1)

            if not createGeoPackage(self.path):
                return False

            if self.createDistLayer():
                self.createUnassigned()
                self.setProgress(2)
            else:
                return False

            if self.createAssignLayer():
                self.importSourceData()
            else:
                return False
        except CancelledError:
            return False
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False
        finally:
            self.popLayer = None
            self.srcLayer = None

        self.setProgress(100)
        return True

    def finished(self, result: bool):
        if not result:
            if self.exception is not None:
                QgsMessageLog.logMessage(
                    f'{self.exception!r}', 'Redistricting', Qgis.Critical)
