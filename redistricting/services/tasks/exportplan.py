# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - background task to add a new geofield

        begin                : 2022-06-01
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

import csv
from contextlib import closing
from typing import (
    TYPE_CHECKING,
    Union
)

from qgis.core import (
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsFeatureRequest,
    QgsFeedback,
    QgsField,
    QgsFields,
    QgsProject,
    QgsTask,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes
)
from qgis.PyQt.QtCore import QMetaType
from qgis.utils import spatialite_connect

from ...models import DistrictColumns
from ...utils import tr
from ._debug import debug_thread

if TYPE_CHECKING:
    from ...models import (
        RdsDataField,
        RdsField,
        RdsPlan
    )


def makeDbfFieldName(fieldName, fields: QgsFields):
    if len(fieldName) <= 10:
        return fieldName

    fn = fieldName[:10]
    i = 0
    while fields.lookupField(fn) != -1:
        i += 1
        suff = str(i)
        fn = fieldName[:10-len(suff)] + suff

    return fn


class ExportRedistrictingPlanTask(QgsTask):
    def __init__(
        self,
        plan: RdsPlan,
        exportShape: bool = True,
        shapeFileName: str = None,
        includeDemographics: bool = True,
        includeMetrics: bool = True,
        includeUnassigned: bool = False,
        exportEquivalency: bool = True,
        equivalencyFileName: str = None,
        assignGeography: RdsField = None
    ):
        super().__init__(tr('Export assignments'), QgsTask.AllFlags)
        self.exportShape = exportShape and shapeFileName and plan.distLayer
        self.shapeFileName = shapeFileName
        self.includeDemographics = includeDemographics
        self.includeMetrics = includeMetrics
        self.includeUnassigned = includeUnassigned

        self.exportEquivalency = exportEquivalency and equivalencyFileName and plan.assignLayer
        self.equivalencyFileName = equivalencyFileName
        self.assignGeography = assignGeography

        self.assignLayer = plan.assignLayer
        self.geoIdField = plan.geoIdField
        self.distField = plan.distField

        self.distLayer = plan.distLayer

        self.popField = plan.popField
        self.popFields = plan.popFields
        self.dataFields = plan.dataFields

        self.districts = plan.districts

        self.exception = None

    def _createFields(self, context: QgsExpressionContext):
        fields = QgsFields()
        fieldNames = {
            self.distField: makeDbfFieldName(self.distField, fields),
            'name': 'name',
            'members': 'members'
        }
        fields.append(QgsField(fieldNames[self.distField], QMetaType.Int))
        fields.append(QgsField('name', QMetaType.QString, 'QString', 127))
        fields.append(QgsField("members", QMetaType.Int))

        if self.includeDemographics:
            fieldNames |= {
                'population': 'population',
                'deviation': 'deviation',
                'pct_deviation': 'pct_dev'
            }
            fields.append(QgsField('population', QMetaType.LongLong, 'Integer64', 18, 0))
            fields.append(QgsField('deviation', QMetaType.Double))
            fields.append(QgsField('pct_dev', QMetaType.Double))

            for f in self.popFields:
                f.prepare(context)
                fn = f.fieldName
                fieldNames[fn] = makeDbfFieldName(fn, fields)
                field = f.makeQgsField(fieldNames[fn])
                if field.type() in (QMetaType.LongLong, QMetaType.ULongLong, QMetaType.Long):
                    field.setTypeName('Integer64')
                    field.setLength(20)
                    field.setPrecision(0)
                fields.append(field)

            for f in self.dataFields:
                f.prepare(context)
                fn = f.fieldName
                fieldNames[fn] = makeDbfFieldName(fn, fields)
                field = f.makeQgsField(fieldNames[fn])
                if field.type() in (QMetaType.LongLong, QMetaType.ULongLong, QMetaType.Long):
                    field.setTypeName('Integer64')
                    field.setLength(20)
                    field.setPrecision(0)
                fields.append(field)
                if f.pctBase:
                    fn = f'pct_{f.fieldName}'
                    fieldNames[fn] = makeDbfFieldName(f'p_{f.fieldName}', fields)
                    fields.append(QgsField(fieldNames[fn], QMetaType.Double))

        if self.includeMetrics:
            fieldNames |= {
                'polsbypopper': 'polsbypop',
                'reock': 'reock',
                'convexhull': 'convexhull'
            }
            fields.append(QgsField('polsbypop', QMetaType.Double))
            fields.append(QgsField('reock', QMetaType.Double))
            fields.append(QgsField('convexhull', QMetaType.Double))
        return fields, fieldNames

    def _createDistrictsMemoryLayer(self):
        def fieldByName(fieldName, fieldList: list[RdsField]) -> Union[RdsField, RdsDataField]:
            for f in fieldList:
                if f.field == fieldName:
                    return f
            return None

        if not self.includeUnassigned:
            flt = f'{self.distField} != 0 AND {self.distField} IS NOT NULL'
        else:
            flt = None

        layer = QgsVectorLayer(f'MultiPolygon?crs={self.distLayer.crs()}&index=yes', 'tempshape', 'memory')
        layer.setCrs(self.distLayer.crs())

        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.distLayer))
        fields, fieldNames = self._createFields(context)

        pr = layer.dataProvider()
        pr.addAttributes(fields)
        layer.updateFields()

        if flt:
            expr = QgsExpression(flt)
            request = QgsFeatureRequest(expr, context)
        else:
            request = QgsFeatureRequest()

        if not self.includeDemographics or not self.includeMetrics:
            request.setSubsetOfAttributes(fieldNames, self.distLayer.fields())

        features = []
        for f in self.distLayer.getFeatures(request):
            if (dist := self.districts[f['district']]) is not None:
                feat = QgsFeature()
                data = []
                for srcFld in fieldNames:
                    if srcFld[:3] == "pct" and srcFld != DistrictColumns.PCT_DEVIATION:
                        basefld = srcFld[4:]
                        pctbase = fieldByName(basefld, self.dataFields).pctBase
                        if pctbase == self.popField:
                            pctbase = DistrictColumns.POPULATION
                        if dist[basefld] is None or not dist[pctbase]:
                            data.append(0)
                        else:
                            data.append(dist[basefld] / dist[pctbase])
                    else:
                        data.append(dist[srcFld])
                feat.setAttributes(data)
                feat.setGeometry(f.geometry())
                features.append(feat)

        success, _ = pr.addFeatures(features)
        if success:
            layer.updateExtents()
        else:
            self.exception = RuntimeError(
                tr("Error when creating shapefile: {}").format(pr.lastError())
            )

        return layer if success else None

    def _exportShapeFile(self):
        """Write shapefile"""

        layer = self._createDistrictsMemoryLayer()
        if layer is not None:
            saveOptions = QgsVectorFileWriter.SaveVectorOptions()
            saveOptions.driverName = "ESRI Shapefile"
            saveOptions.fileEncoding = "UTF-8"
            saveOptions.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
            feedback = QgsFeedback()
            feedback.progressChanged.connect(self.setProgress)
            if self.canCancel():
                feedback.canceled.connect(self.cancel)
            saveOptions.feedback = feedback

            error, msg, _fn, _ln = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer,
                self.shapeFileName,
                QgsProject.instance().transformContext(),
                saveOptions,
            )

            if error != QgsVectorFileWriter.NoError:
                self.exception = RuntimeError(msg)
                return False
        else:
            return False

        return True

    def _exportEquivalency(self):
        if self.assignGeography:
            geoPackagePath = self.assignLayer.dataProvider().dataSourceUri().split('|')[0]
            with closing(spatialite_connect(geoPackagePath)) as db:
                sql = f'SELECT DISTINCT {self.assignGeography.fieldName}, {self.distField} ' \
                    f'FROM assignments ORDER BY {self.assignGeography.fieldName}'
                c = db.execute(sql)
                total = c.rowcount
                count = 0
                chunkSize = total // 100

                with open(self.equivalencyFileName, 'w+', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([self.assignGeography.fieldName, tr('district')])
                    while chunk := c.fetchmany(chunkSize):
                        writer.writerows(chunk)
                        count += 1
                        self.setProgress(count/total)
        else:
            saveOptions = QgsVectorFileWriter.SaveVectorOptions()
            saveOptions.driverName = "csv"
            saveOptions.fileEncoding = "UTF-8"
            saveOptions.overrideGeometryType = QgsWkbTypes.NoGeometry
            saveOptions.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
            saveOptions.attributes = [
                self.assignLayer.fields().indexFromName(self.geoIdField),
                self.assignLayer.fields().indexFromName(self.distField)
            ]
            feedback = QgsFeedback()
            feedback.progressChanged.connect(self.setProgress)
            if self.canCancel():
                feedback.canceled.connect(self.cancel)
            saveOptions.feedback = feedback

            error, msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
                layer=self.assignLayer,
                fileName=self.equivalencyFileName,
                transformContext=QgsProject.instance().transformContext(),
                options=saveOptions
            )

            if error != QgsVectorFileWriter.NoError:
                self.exception = RuntimeError(msg)
                return False

        return True

    def run(self) -> bool:
        debug_thread()
        try:
            if self.exportShape:
                if not self._exportShapeFile():
                    return False

            if self.exportEquivalency:
                if not self._exportEquivalency():
                    return False

            self.setProgress(100)
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

        return True
