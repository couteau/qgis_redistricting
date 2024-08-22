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
    Any,
    Iterable,
    Optional,
    Union
)

import geopandas as gpd
import pandas as pd
from qgis.core import (
    QgsApplication,
    QgsFeatureRequest,
    QgsTask
)
from qgis.PyQt.QtCore import (
    QObject,
    QSignalMapper,
    pyqtSignal
)

from .Tasks import AggregateDistrictDataTask

if TYPE_CHECKING:
    from ..models.Plan import RdsPlan


class DistrictUpdater(QObject):
    updateStarted = pyqtSignal("PyQt_PyObject", "PyQt_PyObject")  # plan, districts
    updateComplete = pyqtSignal("PyQt_PyObject", "PyQt_PyObject")  # plan, districts
    updateTerminated = pyqtSignal("PyQt_PyObject", bool, "PyQt_PyObject")  # plan, canceled, exception

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._updateTasks: dict["RdsPlan", AggregateDistrictDataTask] = {}
        self._updateDistricts: dict["RdsPlan", set[int]] = {}
        self._beforeCommitSignals = QSignalMapper(self)
        self._beforeCommitSignals.mappedObject.connect(self.checkForChangedAssignments)
        self._afterCommitSignals = QSignalMapper(self)
        self._afterCommitSignals.mappedObject.connect(self.startUpdateDistricts)

    def updateDistrictData(self, plan: "RdsPlan", data: Union[pd.DataFrame, gpd.GeoDataFrame]):
        for district, row in data.to_dict(orient="index").items():
            plan.districts[district].update(row)

    def updateStats(self, plan: "RdsPlan", totalPopulation: int, cutEdges: int, splitsData: dict[str, pd.DataFrame]):
        plan.stats.updateStats(totalPopulation, cutEdges, splitsData)

    def updateTaskCompleted(self):
        updateTask: AggregateDistrictDataTask = self.sender()
        del self._updateTasks[updateTask.plan]

        if updateTask.data is not None:
            self.updateDistrictData(updateTask.plan, updateTask.data)
        if updateTask.totalPopulation != 0 or updateTask.cutEdges != 0 or updateTask.splits is not None:
            self.updateStats(updateTask.plan, updateTask.totalPopulation, updateTask.cutEdges, updateTask.splits)

        updated = list(updateTask.updateDistricts) if updateTask.updateDistricts else None
        self.updateComplete.emit(updateTask.plan, updated)

    def updateTaskTerminated(self):
        updateTask: AggregateDistrictDataTask = self.sender()
        del self._updateTasks[updateTask.plan]
        self.updateTerminated.emit(updateTask.plan, updateTask.isCanceled(), updateTask.exception)

    def planIsUpdating(self, plan):
        return plan in self._updateTasks and self._updateTasks[plan].status() < QgsTask.Complete

    def cancelUpdate(self, plan):
        if plan in self._updateTasks:
            task = self._updateTasks[plan]
            task.cancel()
            task.waitForFinished()
            del self._updateTasks[plan]

    def updateDistricts(
            self,
            plan: "RdsPlan",
            districts: Optional[Iterable[int]] = None,
            needDemographics=False,
            needGeometry=False,
            needSplits=False,
            force=False
    ):
        """ update aggregate district data from assignments, including geometry where requested

        :param plan: Plan to update
        :type plan: RdsPlan

        :param districts: Districts of plan to update if less than all districts
        :type districts: Iterable[int] | None

        :param needDemographics: Plan needs district demographics updated
        :type needDemographics: bool

        :param needGeometry: Plan needs district geometry and related metrics updated
        :type needGeometry: bool

        :param needSplits: Plan needs subdivision splits updated
        :type needSplits: bool

        :param force: Cancel any pending update and begin a new update
        :type force: bool
        """
        if not (needDemographics or needGeometry or needSplits):
            return

        if force and self.planIsUpdating(plan):
            self.cancelUpdate(plan)

        if not self.planIsUpdating(plan):
            districts = set(districts) if districts is not None else set()
            self.updateStarted.emit(plan, list(districts))
            updateTask = AggregateDistrictDataTask(
                plan,
                updateDistricts=districts,
                includeGeometry=needGeometry,
                includeDemographics=needDemographics,
                includSplits=needSplits
            )
            updateTask.taskCompleted.connect(self.updateTaskCompleted)
            updateTask.taskTerminated.connect(self.updateTaskTerminated)
            self._updateTasks[plan] = updateTask
            QgsApplication.taskManager().addTask(updateTask)

    def watchPlan(self, plan: "RdsPlan"):
        if plan.assignLayer:
            self._beforeCommitSignals.setMapping(plan.assignLayer, plan)
            self._afterCommitSignals.setMapping(plan.assignLayer, plan)
            plan.assignLayer.beforeCommitChanges.connect(self._beforeCommitSignals.map)
            plan.assignLayer.afterCommitChanges.connect(self._afterCommitSignals.map)

    def unwatchPlan(self, plan: "RdsPlan"):
        if plan.assignLayer:
            plan.assignLayer.beforeCommitChanges.disconnect(self._beforeCommitSignals.map)
            plan.assignLayer.afterCommitChanges.disconnect(self._afterCommitSignals.map)
            self._beforeCommitSignals.removeMappings(plan.assignLayer)
            self._afterCommitSignals.removeMappings(plan.assignLayer)

    def checkForChangedAssignments(self, plan: "RdsPlan"):
        dindex = plan.assignLayer.fields().lookupField(plan.distField)
        if dindex == -1:
            return

        new = {}
        changedAttrs: dict[int, dict[int, Any]] = plan.assignLayer.editBuffer().changedAttributeValues()
        for fid, attrs in changedAttrs.items():
            for fld, value in attrs.items():
                if fld == dindex:
                    new[fid] = value

        old = {
            f[dindex] for f in plan.assignLayer.dataProvider().getFeatures(QgsFeatureRequest(list(new.keys())))
        }
        self._updateDistricts[plan] = set(new.values()) | old

    def startUpdateDistricts(self, plan: "RdsPlan"):
        if self._updateDistricts[plan]:
            self.updateDistricts(plan, self._updateDistricts[plan], True, True, True)
            del self._updateDistricts[plan]
