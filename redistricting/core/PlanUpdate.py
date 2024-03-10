"""QGIS Redistricting Plugin - plan updater

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
from typing import (
    TYPE_CHECKING,
    Optional,
    Union
)

import pandas as pd
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsFeatureRequest,
    QgsTask,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)

from .Tasks import AggregateDistrictDataTask

if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class PlanUpdater(QObject):
    updateStarted = pyqtSignal()
    updateComplete = pyqtSignal()
    updateTerminated = pyqtSignal(bool)

    def __init__(self, plan: "RedistrictingPlan"):
        super().__init__(plan)
        self._plan = plan
        self._updateTask: Optional[AggregateDistrictDataTask] = None
        self._needDemographicUpdate = False
        self._needGeometryUpdate = False
        self._updateDistricts = set[int]()
        self._assignLayer: QgsVectorLayer = None
        self._dindex: int = -1

    def clear(self):
        self._needDemographicUpdate = False
        self._needGeometryUpdate = False
        self._updateDistricts = set[int]()

    def setAssignLayer(self, value: QgsVectorLayer):
        if self._assignLayer is not None:
            self._assignLayer.beforeCommitChanges.disconnect(self.updateChangedDistricts)
            self._assignLayer.afterCommitChanges.disconnect(self.startUpdate)
            self._dindex = -1

        self._assignLayer = value

        if self._assignLayer is not None:
            self._dindex = self._assignLayer.fields().indexFromName(self._plan.distField)
            self._assignLayer.beforeCommitChanges.connect(self.updateChangedDistricts)
            self._assignLayer.afterCommitChanges.connect(self.startUpdate)

    def updateTaskCompleted(self):
        if self._updateTask.totalPopulation:
            self._plan.updateTotalPopulation(self._updateTask.totalPopulation)

        self._plan.updateDistrictData(self._updateTask.data)
        self._plan.updateSplitsData(self._updateTask.cutEdges, self._updateTask.splits)

        self.clear()

        self.updateComplete.emit()
        self._updateTask = None

    def updateTaskTerminated(self):
        if self._updateTask.exception:
            self._plan.setError(f'{self._updateTask.exception!r}', Qgis.Critical)
        self.updateTerminated.emit(self._updateTask.isCanceled())
        self._updateTask = None

    def startUpdate(self, force=False):
        """ update aggregate district data from assignments, including geometry where requested

        :param force: Cancel any pending update and begin a new update
        :type force: bool

        :returns: QgsTask object representing the background update task
        :rtype: QgsTask
        """
        if not (self._needDemographicUpdate or self._needGeometryUpdate):
            return

        if force and self._updateTask:
            self._updateTask.cancel()
            self._updateTask.waitForFinished()
            self._updateTask = None

        if not self._updateTask:
            self._plan.clearErrors()

            self.updateStarted.emit()
            self._updateTask = AggregateDistrictDataTask(
                self._plan,
                updateDistricts=self._updateDistricts,
                includeGeometry=self._needGeometryUpdate
            )
            self._updateTask.taskCompleted.connect(self.updateTaskCompleted)
            self._updateTask.taskTerminated.connect(self.updateTaskTerminated)
            QgsApplication.taskManager().addTask(self._updateTask)

    def updateDistricts(
            self,
            districts: Union[int, set[int]] = None,
            immediate: bool = False
    ):
        if districts is not None:
            if isinstance(districts, int):
                districts = {districts}
            self._updateDistricts |= districts

        self._needGeometryUpdate = True
        if immediate:
            self.startUpdate()

    def updateChangedDistricts(self):
        changedAttrs = self._assignLayer.editBuffer().changedAttributeValues()
        new = pd.DataFrame.from_dict(changedAttrs).transpose()
        if not self._dindex in new.columns:
            return

        new = new[self._dindex].dropna()
        old = {
            f[self._dindex] for f in self._assignLayer.dataProvider().getFeatures(QgsFeatureRequest(list(new.index)))
        }
        self.updateDistricts(set(new) | old)

    def rollbackDistrictChange(self):
        self._updateDistricts = set()
        self._needGeometryUpdate = False

    def updateDemographics(self):
        self._needDemographicUpdate = True
        self.startUpdate()

    @property
    def isUpdating(self):
        return self._updateTask is not None and self._updateTask.status() < QgsTask.Complete
