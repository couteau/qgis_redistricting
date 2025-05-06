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

from typing import Optional

from qgis.core import Qgis, QgsApplication
from qgis.PyQt.QtCore import QObject, pyqtSignal

from ..models import RdsField, RdsPlan
from ..utils import tr
from .errormixin import ErrorListMixin
from .tasks.exportplan import ExportRedistrictingPlanTask


class PlanExporter(ErrorListMixin, QObject):
    exportComplete = pyqtSignal()
    exportTerminated = pyqtSignal()
    progressChanged = pyqtSignal(int)

    def __init__(  # noqa: PLR0913
        self,
        plan: RdsPlan,
        equivalencyFile=None,
        shapeFile=None,
        assignGeography: RdsField = None,
        includeUnassigned=False,
        includeDemographics=False,
        includeMetrics=False,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._plan = plan
        self.equivalencyFile = equivalencyFile
        self.shapeFile = shapeFile
        self.assignGeography = (
            None if assignGeography is None or assignGeography.field == plan.geoIdField else assignGeography
        )
        self.includeUnassigned = includeUnassigned
        self.includeDemographics = includeDemographics
        self.includeMetrics = includeMetrics
        self._exportTask = None

    def setProgress(self, progress: float):
        self.progressChanged.emit(int(progress))

    def cancel(self):
        if self._exportTask:
            self._exportTask.cancel()

    def export(self):
        def taskCompleted():
            self._exportTask = None
            self.exportComplete.emit()

        def taskTerminated():
            if self._exportTask.exception:
                self.setError(str(self._exportTask.exception))
            elif self._exportTask.isCanceled():
                self.setError(tr("Export cancelled"), Qgis.MessageLevel.UserCanceled)
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
            self.assignGeography,
        )

        self._exportTask.progressChanged.connect(self.setProgress)
        self._exportTask.taskCompleted.connect(taskCompleted)
        self._exportTask.taskTerminated.connect(taskTerminated)
        QgsApplication.taskManager().addTask(self._exportTask)

        return self._exportTask
