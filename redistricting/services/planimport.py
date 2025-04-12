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
from typing import (
    TYPE_CHECKING,
    Optional,
    Union
)

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsTask,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    NULL,
    QObject,
    pyqtSignal
)

from ..utils import tr
from .errormixin import ErrorListMixin
from .feedback import Feedback
from .tasks.importequivalency import ImportAssignmentFileTask
from .tasks.importshape import ImportShapeFileTask

if TYPE_CHECKING:
    from ..models import RdsPlan


class PlanImporter(ErrorListMixin, QObject):
    progressChanged = pyqtSignal(int)
    importComplete = pyqtSignal("PyQt_PyObject")
    importTerminated = pyqtSignal("PyQt_PyObject")

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._plan = None
        self._file = None

        self._error = None
        self._errorLevel = None
        self._importTask: QgsTask = None

    def isValid(self) -> bool:
        result = True
        if not self._plan:
            self.pushError(tr('No plan provided to import service'), Qgis.MessageLevel.Critical)
            result = False
        elif not self._plan.isValid():
            self.pushError(tr('Plan must be valid for import'), Qgis.MessageLevel.Critical)
            result = False

        if not self._file:
            self.pushError(tr('Source file is required for import'), Qgis.MessageLevel.Critical)
            result = False
        elif not self._file.exists():
            self.pushError(tr('{file!s} does not exist').format(file=self._file), Qgis.MessageLevel.Critical)
            result = False

        return result

    def setSourceFile(self, value: Union[str, pathlib.Path]):
        if isinstance(value, str):
            self._file = pathlib.Path(value).resolve(strict=False)
        elif isinstance(value, pathlib.Path):
            self._file = value.resolve()
        else:
            raise ValueError(tr('Invalid type for source path'))

        return self

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
        self.importComplete.emit(self._plan)

    def taskTerminated(self):
        if self._importTask.exception:
            self.pushError(f'{self._importTask.exception!r}')
        elif self._importTask.isCanceled():
            self.setError(tr('Import cancelled'), Qgis.UserCanceled)
        self._importTask = None
        self.importTerminated.emit(self._plan)

    def importPlan(self, plan: "RdsPlan", startTask: bool = True):
        self.clearErrors()

        self._plan = plan

        if not self.isValid():
            return None

        if self._plan.assignLayer.isEditable():
            self.setError(tr('Committing unsaved changes before import'))
            self._plan.assignLayer.commitChanges(True)

        self._importTask = self._createImportTask()
        self._importTask.taskCompleted.connect(self.taskCompleted)
        self._importTask.taskTerminated.connect(self.taskTerminated)
        self._importTask.progressChanged.connect(self.setProgress)

        if startTask:
            self.startImport()

        return self._importTask

    def startImport(self):
        QgsApplication.taskManager().addTask(self._importTask)


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
        return self

    def setHeaderRow(self, value: bool):
        self._headerRow = value
        return self

    def setGeoColumn(self, value: int):
        self._geoColumn = value
        return self

    def setDistColumn(self, value: int):
        self._distColumn = value
        return self

    def setDelimiter(self, value: str):
        self._delimiter = value
        return self

    def setQuoteChar(self, value: str):
        self._quotechar = value
        return self

    def isValid(self) -> bool:
        result = super().isValid()
        if result:
            if self._joinField is None:
                self._joinField = self._plan.geoIdField

            mimetype, _ = mimetypes.guess_type(self._file)
            result = mimetype.startswith((
                'text/plain',
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

    def isValid(self) -> bool:
        result = super().isValid()

        if result:
            self._layer = QgsVectorLayer(str(self._file), '__import_layer')
            self._layer.setParent(self)
            if not self._layer.isValid() or self._layer.dataProvider().storageType() != 'ESRI Shapefile':
                self.pushError(tr('Invalid shapefile for import: {file!s}').format(
                    file=self._file), Qgis.MessageLevel.Critical)
                result = False
            elif not self._distField or self._layer.fields().lookupField(self._distField) == -1:
                self.pushError(tr('Field {field} not found in shapefile {file!s}').format(
                    field=self._distField, file=self._file), Qgis.MessageLevel.Critical)
                result = False

        if result:
            if self._nameField and self._layer.fields().lookupField(self._nameField) == -1:
                self.pushError((tr('Field {field} not found in shapefile {file}') + tr('--Ignoring.')).format(
                    field=self._nameField, file=self._file), Qgis.MessageLevel.Warning)
                self._nameField = None

            if self._membersField and self._layer.fields().lookupField(self._membersField) == -1:
                self.pushError((tr('Field {field} not found in shapefile {file}') + tr('--Ignoring.')).format(
                    field=self._membersField, file=self._file), Qgis.MessageLevel.Warning)
                self._membersField = None

        return result

    def setDistField(self, value: str):
        self._distField = value
        return self

    def setNameField(self, value: str):
        self._nameField = value
        return self

    def setMembersField(self, value: str):
        self._membersField = value
        return self

    def _createImportTask(self):
        return ImportShapeFileTask(self._plan, str(self._file), self._distField)

    def taskCompleted(self):
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
                d = self._plan.districts[dist]
                d.name = name
                d.members = members
        super().taskCompleted()


class PlanImportService(QObject):
    importComplete = pyqtSignal("PyQt_PyObject")
    importTerminated = pyqtSignal("PyQt_PyObject")

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._tasks: dict[RdsPlan, QgsTask] = {}

    def removeTask(self, plan):
        if plan in self._tasks:
            del self._tasks[plan]

    def completed(self, plan):
        self.removeTask(plan)
        self.importComplete.emit(plan)

    def terminated(self, plan):
        self.removeTask(plan)
        self.importTerminated.emit(plan)

    def importEquivalencyFile(
        self,
        plan: RdsPlan,
        source: Union[str, pathlib.Path],
        joinField: str,
        headerRow: bool = True,
        geoColumn: int = 0,
        distColumn: int = 1,
        delimiter: str = None,
        quotechar: str = None,
        progress: Feedback = None,
        startTask: bool = True
    ):
        if plan in self._tasks and self._tasks[plan].status() < QgsTask.Complete:
            return None

        importer = AssignmentImporter(self)
        importer.importComplete.connect(self.completed)
        importer.importTerminated.connect(self.terminated)
        if progress:
            importer.progressChanged.connect(progress.setValue)
            progress.canceled.connect(importer.cancel)

        importer.setSourceFile(source)\
            .setJoinField(joinField)\
            .setHeaderRow(headerRow)\
            .setGeoColumn(geoColumn)\
            .setDistColumn(distColumn)

        if delimiter is not None:
            importer.setDelimiter(delimiter)
        if quotechar is not None:
            importer.setQuoteChar(quotechar)

        task = importer.importPlan(plan, startTask)
        self._tasks[plan] = task

        return importer

    def importShapeFile(
        self,
        plan,
        source: Union[str, pathlib.Path],
        distField: str,
        nameField: str,
        membersField: str,
        progress: Feedback = None,
        startTask: bool = True
    ):
        if plan in self._tasks and self._tasks[plan].status() < QgsTask.Complete:
            return None

        importer = ShapefileImporter(self)
        importer.importComplete.connect(self.completed)
        importer.importTerminated.connect(self.terminated)
        if progress:
            importer.progressChanged.connect(progress.setValue)
            progress.canceled.connect(importer.cancel)

        importer.setSourceFile(source)\
            .setDistField(distField)\
            .setNameField(nameField)\
            .setMembersField(membersField)

        if plan is not None and startTask:
            self.startImport(plan, importer)

        return importer

    def startImport(self, plan, importer: PlanImporter, progress: Feedback = None):
        if progress:
            importer.progressChanged.connect(progress.setValue)
            progress.canceled.connect(importer.cancel)

        task = importer.importPlan(plan)
        self._tasks[plan] = task
        return task
