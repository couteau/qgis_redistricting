# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - import assignment file or shapefile to plan

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

import mimetypes
import pathlib
from typing import Union

from qgis.PyQt.QtCore import QObject, pyqtSignal, NULL
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsTask,
    QgsVectorLayer
)
from .utils import tr
from .ErrorList import ErrorListMixin
from .Tasks import ImportAssignmentFileTask, ImportShapeFileTask
from . import District, RedistrictingPlan


class PlanImporter(ErrorListMixin, QObject):
    progressChanged = pyqtSignal(int)
    importComplete = pyqtSignal()
    importTerminated = pyqtSignal()

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._plan = None
        self._file = None

        self._error = None
        self._errorLevel = None
        self._importTask: QgsTask = None

    def _isValid(self) -> bool:
        result = True
        if not self._plan:
            self.pushError(tr('No plan provided to import service'), Qgis.Critical)
            result = False
        elif not self._plan.isValid():
            self.pushError(tr('Plan must be valid for import'), Qgis.Critical)
            result = False

        if not self._file:
            self.pushError(tr('Source file is required for import'), Qgis.Critical)
            result = False
        elif not self._file.exists():
            self.pushError(tr('{file!s} does not exist').format(file=self._file), Qgis.Critical)
            result = False

        return result

    def setSourceFile(self, value: Union[str, pathlib.Path]):
        if isinstance(value, str):
            self._file = pathlib.Path(value).resolve(strict=False)
        elif isinstance(value, pathlib.Path):
            self._file = value.resolve()
        else:
            raise ValueError(tr('Invalid type for source path'))

    def setProgress(self, progress: float):
        self.progressChanged.emit(int(progress))

    def cancel(self):
        if self._importTask:
            self._importTask.cancel()

    def _createImportTask(self) -> QgsTask:
        raise NotImplementedError()

    def taskCompleted(self):
        self.setProgress(100)
        self._importTask = None
        self._plan.resetData(updateGeometry=True, immediate=True)
        self.importComplete.emit()

    def taskTerminated(self):
        if self._importTask.exception:
            self.pushError(f'{self._importTask.exception!r}')
        elif self._importTask.isCanceled():
            self.setError(tr('Import cancelled'), Qgis.UserCanceled)
        self._importTask = None
        self.importTerminated.emit()

    def importPlan(self, plan: RedistrictingPlan):
        self.clearErrors()

        self._plan = plan

        if not self._isValid():
            return None

        if self._plan.assignLayer.isEditable():
            self.setError(tr('Committing unsaved changes before import'))
            self._plan.assignLayer.commitChanges(True)

        self._importTask = self._createImportTask()
        self._importTask.taskCompleted.connect(self.taskCompleted)
        self._importTask.taskTerminated.connect(self.taskTerminated)
        self._importTask.progressChanged.connect(self.setProgress)

        QgsApplication.taskManager().addTask(self._importTask)

        return self._importTask


class AssignmentImporter(PlanImporter):

    def __init__(self, parent: QObject = None):
        super().__init__(parent)

        self._joinField: str = None
        self._headerRow = True
        self._geoColumn = 0
        self._distColumn = 1
        self._delimiter = None
        self._quotechar = None

    def setJoinField(self, value: str):
        self._joinField = value

    def setHeaderRow(self, value: bool):
        self._headerRow = value

    def setGeoColumn(self, value: int):
        self._geoColumn = value

    def setDistColumn(self, value: int):
        self._distColumn = value

    def setDelimiter(self, value: str):
        self._delimiter = value

    def setQuoteChar(self, value: str):
        self._quotechar = value

    def _isValid(self) -> bool:
        result = super()._isValid()
        if result:
            if self._joinField is None:
                self._joinField = self._plan.geoIdField

            mimetype, _ = mimetypes.guess_type(self._file)
            result = mimetype.startswith((
                'text/plan',
                'text/csv',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml',
                'application/vnd.oasis.opendocument.spreadsheet'
            ))

        return result

    def _createImportTask(self):
        if self._plan.assignLayer.isEditable():
            self.pushError(tr('Committing unsaved changes before import'))
            self._plan.assignLayer.commitChanges(True)

        return ImportAssignmentFileTask(
            self._plan, self._file, self._headerRow, self._geoColumn, self._distColumn,
            self._delimiter, self._quotechar, self._joinField)


class ShapefileImporter(PlanImporter):
    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._distField: str = None
        self._nameField: str = None
        self._membersField: str = None
        self._layer: QgsVectorLayer = None

    def _isValid(self) -> bool:
        result = super()._isValid()

        if result:
            self._layer = QgsVectorLayer(str(self._file), '__import_layer')
            if not self._layer.isValid() or self._layer.dataProvider().storageType() != 'ESRI Shapefile':
                self.pushError(tr('Invalid shapefile for import: {file!s}').format(file=self._file), Qgis.Critical)
                result = False
            elif not self._distField or self._layer.fields().lookupField(self._distField) == -1:
                self.pushError(tr('Field {field} not found in shapefile {file!s}').format(
                    field=self._distField, file=self._file), Qgis.Critical)
                result = False

        if result:
            if self._nameField and self._layer.fields().lookupField(self._nameField) == -1:
                self.pushError((tr('Field {field} not found in shapefile {file}') + tr('--Ignoring.')).format(
                    field=self._nameField, file=self._file), Qgis.Warning)
                self._nameField = None

            if self._membersField and self._layer.fields().lookupField(self._membersField) == -1:
                self.pushError((tr('Field {field} not found in shapefile {file}') + tr('--Ignoring.')).format(
                    field=self._membersField, file=self._file), Qgis.Warning)
                self._membersField = None

        return result

    def setDistField(self, value: str):
        self._distField = value

    def setNameField(self, value: str):
        self._nameField = value

    def setMembersField(self, value: str):
        self._membersField = value

    def _createImportTask(self):
        return ImportShapeFileTask(self._plan, self._file, self._distField)

    def taskCompleted(self):
        districts = {}
        for f in self._layer.getFeatures():
            dist = f[self._distField]
            if dist == NULL:
                dist = 0
            elif isinstance(dist, str) and dist.isnumeric():
                dist = int(dist)
            elif not isinstance(dist, int):
                dist = f.id()+1

            name = f[self._nameField] if self._nameField else None
            members = f[self._membersField] if self._membersField else 1
            if dist != 0:
                districts[dist] = District(self._plan, dist, name, members)
        self._plan.districts = districts
        super().taskCompleted()
