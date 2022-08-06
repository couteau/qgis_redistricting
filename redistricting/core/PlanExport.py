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
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.PyQt.QtWidgets import QProgressDialog
from qgis.core import Qgis, QgsApplication
from .utils import tr
from .ErrorList import ErrorListMixin
from .Field import Field
from .Tasks import ExportRedistrictingPlanTask
from .Plan import RedistrictingPlan


class PlanExporter(ErrorListMixin, QObject):
    exportComplete = pyqtSignal()
    exportTerminated = pyqtSignal()

    def __init__(
        self,
        plan: RedistrictingPlan,
        equivalencyFile=None,
        shapeFile=None,
        assignGeography: Field = None,
        includeUnassigned=False,
        includeDemographics=False,
        includeMetrics=False
    ):
        super().__init__(plan)
        self._plan = plan
        self.equivalencyFile = equivalencyFile
        self.shapeFile = shapeFile
        self.assignGeography = \
            None if assignGeography is None or assignGeography.field == plan.geoIdField \
            else assignGeography
        self.includeUnassigned = includeUnassigned
        self.includeDemographics = includeDemographics
        self.includeMetrics = includeMetrics
        self._exportTask = None

    def export(self, progress: QProgressDialog = None):
        def taskCompleted():
            if progress:
                progress.canceled.disconnect(self._exportTask.cancel)
                progress.setValue(100)
            self._exportTask = None
            self.exportComplete.emit()

        def taskTerminated():
            if progress:
                progress.hide()
                progress.canceled.disconnect(self._exportTask.cancel)
            if self._exportTask.exception:
                self.setError(str(self._exportTask.exception))
            elif self._exportTask.isCanceled():
                self.setError(tr('Export cancelled'), Qgis.UserCanceled)
            self._exportTask = None
            self.exportTerminated.emit()

        self.clearErrors()

        self._exportTask = ExportRedistrictingPlanTask(
            self._plan,
            bool(self.shapeFile),
            self.shapeFile,
            self.includeDemographics,
            self.includeMetrics,
            self.includeUnassigned,
            bool(self.equivalencyFile),
            self.equivalencyFile,
            self.assignGeography
        )
        if progress:
            self._exportTask.progressChanged.connect(lambda p: progress.setValue(int(p)))
            progress.canceled.connect(self._exportTask.cancel)

        self._exportTask.taskCompleted.connect(taskCompleted)
        self._exportTask.taskTerminated.connect(taskTerminated)
        QgsApplication.taskManager().addTask(self._exportTask)

        return self._exportTask
