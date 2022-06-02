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
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from __future__ import annotations

import os
from typing import List, TYPE_CHECKING
from contextlib import closing
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsProject,
    QgsTask,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsField,
    QgsFields,
    QgsFeature,
    QgsVectorLayer,
    QgsVectorFileWriter
)
from qgis.utils import spatialite_connect

from ._exception import CancelledError
from ._debug import debug_thread
from ..Utils import tr
from ..Exception import RdsException

if TYPE_CHECKING:
    from .. import RedistrictingPlan, Field, DataField


class CreatePlanLayersTask(QgsTask):
    def __init__(self, plan: RedistrictingPlan, gpkgPath, srcLayer: QgsVectorLayer, srcGeoIdField: str):
        super().__init__(tr('Create assignments layer'), QgsTask.AllFlags)
        self.path = gpkgPath
        self.srcLayer = srcLayer
        self.srcGeoIdField = srcGeoIdField

        self.geoIdField = plan.geoIdField
        self.distField = plan.distField
        self.geoFields: List[Field] = plan.geoFields

        self.popLayer = plan.popLayer
        self.dataFields: List[DataField] = plan.dataFields
        self.popField = plan.popField
        self.vapField = plan.vapField
        self.cvapField = plan.cvapField

        self.exception = None

    def _createDistLayer(self, gpkgPath):
        l = QgsVectorLayer(
            f'MultiPolygon?crs={self._sourceLayer.sourceCrs().authid()}&index=yes', 'districts', 'memory'
        )
        provider = l.dataProvider()

        fields = [
            QgsField(self.distField, QVariant.Int, 'SMALLINT'),
            QgsField('name', QVariant.String, 'VARCHAR', 127),
            QgsField(self.popLayer.fields().field(self.popField))
        ]

        if self.vapField:
            fields.append(self.popLayer.fields().field(self.vapField))
        if self.cvapField:
            fields.append(self.popLayer.fields().field(self.cvapField))

        context = None
        for f in self.dataFields:
            if f.isExpression:
                context = QgsExpressionContext()
                context.appendScopes(
                    QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))
                context.setFeature(next(self.popLayer.getFeatures()))

            qf = f.makeQgsField(context)
            if qf is None:
                continue
            fields.append(qf)

        fields.append(QgsField('polsbypopper', QVariant.Double))
        fields.append(QgsField('reock', QVariant.Double))
        fields.append(QgsField('convexhull', QVariant.Double))

        provider.addAttributes(fields)
        provider.createSpatialIndex()
        l.updateFields()
        l.updateExtents()

        saveOptions = QgsVectorFileWriter.SaveVectorOptions()
        saveOptions.layerName = 'districts'
        saveOptions.layerOptions = ['GEOMETRY_NAME=geometry']

        # notwithstanding the name of the parameter, actionOnExisting file is not
        # the action to take IF the file exists; it assumes the file exists, so
        # you have to check that yourself or you'll get an error
        if not os.path.exists(gpkgPath):
            saveOptions.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        else:
            saveOptions.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        transformContext = QgsProject.instance().transformContext()
        error = QgsVectorFileWriter.writeAsVectorFormatV2(
            l, gpkgPath, transformContext, saveOptions)

        if error[0] != QgsVectorFileWriter.NoError:
            self.exception = RdsException(
                tr('Error creating new {} layer: {}').format(
                    tr('district'), error[1])
            )
            return False

        return True

    def run(self):
        debug_thread()

        try:
            if not self._createDistLayer(self.path):
                return False

            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.srcLayer))
            context.setFeature(next(self.srcLayer.getFeatures()))

            fields = QgsFields()
            fields.append(QgsField(self.geoIdField, QVariant.String, 'VARCHAR'))
            fields.append(QgsField(self.distField, QVariant.Int, 'INTEGER'))
            for field in self.geoFields:
                qf = field.makeQgsField(context)
                if qf is not None:
                    fields.append(qf)
                else:
                    self.exception = Exception(field.error())

            saveOptions = QgsVectorFileWriter.SaveVectorOptions()
            saveOptions.layerName = 'assignments'
            saveOptions.layerOptions = ['GEOMETRY_NAME=geometry']

            if not os.path.exists(self.path):
                saveOptions.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
            else:
                saveOptions.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

            writer = QgsVectorFileWriter.create(
                self.path,
                fields,
                self.srcLayer.wkbType(),
                self.srcLayer.crs(),
                QgsProject.instance().transformContext(),
                saveOptions)

            if writer.hasError() != QgsVectorFileWriter.NoError:
                self.exception = RdsException(
                    tr("Error when creating assignments layer: {}").format(writer.errorMessage()))
                return False

            total = self.srcLayer.featureCount() or 1
            count = 0
            for f in self.srcLayer.getFeatures():
                if self.isCanceled():
                    raise CancelledError()
                attrs = [f[self.srcGeoIdField], 0] + [field.getValue(f, context) for field in self.geoFields]
                feat = QgsFeature()
                feat.setAttributes(attrs)
                feat.setGeometry(f.geometry())
                writer.addFeature(feat)
                count += 1
                self.setProgress(100 * count/total)

            del writer
        except CancelledError:
            return False
        except Exception as e:  # pylint: disable=broad-except
            print(e)
            self.exception = e
            return False

        self.setProgress(100)
        return True

    def finished(self, result: bool):
        if result:
            with closing(spatialite_connect(self.path)) as db:
                db.execute(
                    f'CREATE UNIQUE INDEX idx_districts_{self.distField} ON districts ({self.distField})')
                db.execute(f'CREATE UNIQUE INDEX idx_assignments_{self.geoIdField} ON assignments ({self.geoIdField})')
                db.execute(f'CREATE INDEX idx_assignments_{self.distField} ON assignments ({self.distField})')
                for field in [field.fieldName for field in self.geoFields]:
                    db.execute(f'CREATE INDEX idx_assignments_{field} ON assignments ({field})')
                db.commit()
