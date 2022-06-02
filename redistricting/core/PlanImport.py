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
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QProgressDialog
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsMessageLog
)
from .Utils import tr
from .Tasks import ImportAssignmentFileTask
if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class PlanImporter():
    importComplete = pyqtSignal()
    importTerminated = pyqtSignal()

    def __init__(
        self,
        plan: RedistrictingPlan,
        file,
        joinField: str = None,
        headerRow=True,
        geoColumn=0,
        distColumn=1,
        delimiter=None,
        quotechar=None,
    ):
        self._plan = plan
        self.file = file
        self.joinField = joinField
        self.headerRow = headerRow,
        self.geoColumn = geoColumn
        self.distColumn = distColumn
        self.delimiter = delimiter
        self.quotechar = quotechar
        self._error = None
        self._errorLevel = None
        self._importTask = None

    def error(self):
        return (self._error, self._errorLevel)

    def setError(self, error, level=Qgis.Warning):
        self._error = error
        self._errorLevel = level
        QgsMessageLog.logMessage(error, 'Redistricting', level)

    def clearError(self):
        self._error = None

    def importAssignments(self, progress: QProgressDialog = None):
        def taskCompleted():
            if progress:
                progress.setValue(100)
                progress.canceled.disconnect(self._importTask.cancel)
            self._importTask = None
            self._plan.districts.resetData(updateGeometry=True, immediate=True)
            self.importComplete.emit()

        def taskTerminated():
            if progress:
                progress.hide()
                progress.canceled.disconnect(self._importTask.cancel)
            if self._importTask.exception:
                self.setError(f'{self._importTask.exception!r}')
            elif self._importTask.isCanceled():
                self.setError(tr('Import cancelled'), Qgis.UserCanceled)
            self._importTask = None
            self.importTerminated.emit()

        self.clearError()

        if not os.path.exists(self.file):
            self.setError(tr(f'{self.file} does not exist'))
            return False

        if self._plan.assignLayer.isEditable():
            self.setError(tr('Committing unsaved changes before import'))
            self._plan.assignLayer.commitChanges(True)

        self._importTask = ImportAssignmentFileTask(  # pylint: disable=attribute-defined-outside-init
            self._plan, self.file, self.headerRow, self.geoColumn, self.distColumn, self.delimiter, self.quotechar, self.joinField)
        self._importTask.taskCompleted.connect(taskCompleted)
        self._importTask.taskTerminated.connect(taskTerminated)
        if progress:
            self._importTask.progressChanged.connect(
                lambda p: progress.setValue(int(p)))
            progress.canceled.connect(self._importTask.cancel)

        QgsApplication.taskManager().addTask(self._importTask)

        return self._importTask
