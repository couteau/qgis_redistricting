# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - export plans

        begin                : 2022-06-01
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
from typing import TYPE_CHECKING

from qgis.PyQt.QtCore import QObject, pyqtSignal, NULL
from qgis.PyQt.QtWidgets import QProgressDialog
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsMessageLog,
    QgsVectorLayer
)
from .Utils import tr
from .Tasks import ImportAssignmentFileTask, ImportShapeFileTask
from . import District
if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class PlanImporter(QObject):
    importComplete = pyqtSignal()
    importTerminated = pyqtSignal()

    def __init__(
        self,
        plan: RedistrictingPlan
    ):
        super().__init__(plan)
        self._plan = plan
        self._error = None
        self._errorLevel = None
        self._importTask = None
        self._progress: QProgressDialog = None

    def error(self):
        return (self._error, self._errorLevel)

    def setError(self, error, level=Qgis.Warning):
        self._error = error
        self._errorLevel = level
        QgsMessageLog.logMessage(error, 'Redistricting', level)

    def clearError(self):
        self._error = None

    def taskCompleted(self):
        if self._progress:
            self._progress.setValue(100)
            self._progress.canceled.disconnect(self._importTask.cancel)
        self._importTask = None
        self._plan.districts.resetData(updateGeometry=True, immediate=True)
        self.importComplete.emit()

    def taskTerminated(self):
        if self._progress:
            self._progress.hide()
            self._progress.canceled.disconnect(self._importTask.cancel)
        if self._importTask.exception:
            self.setError(f'{self._importTask.exception!r}')
        elif self._importTask.isCanceled():
            self.setError(tr('Import cancelled'), Qgis.UserCanceled)
        self._importTask = None
        self.importTerminated.emit()

    def importAssignments(self,
                          file,
                          joinField: str = None,
                          headerRow=True,
                          geoColumn=0,
                          distColumn=1,
                          delimiter=None,
                          quotechar=None,
                          progress: QProgressDialog = None):

        self.clearError()

        if not os.path.exists(file):
            self.setError(tr(f'{file} does not exist'))
            return False

        if self._plan.assignLayer.isEditable():
            self.setError(tr('Committing unsaved changes before import'))
            self._plan.assignLayer.commitChanges(True)

        self._progress = progress
        self._importTask = ImportAssignmentFileTask(
            self._plan, file, headerRow, geoColumn, distColumn,
            delimiter, quotechar, joinField)
        self._importTask.taskCompleted.connect(self.taskCompleted)
        self._importTask.taskTerminated.connect(self.taskTerminated)
        if progress:
            self._importTask.progressChanged.connect(
                lambda p: progress.setValue(int(p)))
            progress.canceled.connect(self._importTask.cancel)

        QgsApplication.taskManager().addTask(self._importTask)

        return self._importTask

    def importShapefile(
        self,
        file,
        distField: str,
        nameField: str = None,
        membersField: str = None,
        progress: QProgressDialog = None
    ):
        self.clearError()

        if not os.path.exists(file):
            self.setError(tr(f'{file} does not exist'))
            return False

        layer = QgsVectorLayer(file)
        if not layer.isValid() or layer.dataProvider().storageType() != 'ESRI Shapefile':
            self.setError(tr('Invalid shapefile for import: {file}').format(file=file), Qgis.Critical)
            return False

        if layer.fields().lookupField(distField) == -1:
            self.setError(tr('Field {field} not found in shapefile {file}').format(
                field=distField, file=file), Qgis.Critical)
            return False

        if self._plan.assignLayer.isEditable():
            self.setError(tr('Committing unsaved changes before import'))
            self._plan.assignLayer.commitChanges(True)

        if nameField and layer.fields().lookupField(nameField) == -1:
            self.setError(tr('Field {field} not found in shapefile {file}').format(
                field=nameField, file=file), Qgis.Warning)
            nameField = None
        if membersField and layer.fields().lookupField(membersField) == -1:
            self.setError(tr('Field {field} not found in shapefile {file}').format(
                field=membersField, file=file), Qgis.Warning)
            membersField = None

        districts = {}
        for f in layer.getFeatures():
            dist = f[distField]
            if dist == NULL:
                dist = 0
            elif isinstance(dist, str) and dist.isnumeric():
                dist = int(dist)
            elif not isinstance(dist, int):
                dist = f.id()+1

            name = f[nameField] if nameField else None
            members = f[membersField] if membersField else 1
            if dist != 0:
                districts[dist] = District(self._plan, dist, name, members)
        self._plan.districts = districts

        self._progress = progress
        self._importTask = ImportShapeFileTask(self._plan, file, distField)
        self._importTask.taskCompleted.connect(self.taskCompleted)
        self._importTask.taskTerminated.connect(self.taskTerminated)
        if progress:
            self._importTask.progressChanged.connect(
                lambda p: progress.setValue(int(p)))
            progress.canceled.connect(self._importTask.cancel)

        QgsApplication.taskManager().addTask(self._importTask)

        return self._importTask
