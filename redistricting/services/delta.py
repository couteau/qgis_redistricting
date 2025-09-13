"""QGIS Redistricting Plugin - monitor assignment changes and update delta object

        begin                : 2024-05-12
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Cryptodira
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

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
from qgis.core import QgsFeedback, QgsTask
from qgis.PyQt.QtCore import QObject, QSignalMapper, pyqtSignal

from ..models import DeltaList, DistrictColumns, RdsPlan
from ..utils import spatialite_connect
from ..utils.misc import quote_identifier
from .errormixin import ErrorListMixin
from .planmgr import PlanManager
from .updateservice import IncrementalFeedback, UpdateParams, UpdateService


@dataclass
class DeltaUpdate(UpdateParams):
    plan: RdsPlan
    assignments: Optional[pd.DataFrame] = None
    popData: Optional[pd.DataFrame] = None
    data: Optional[pd.DataFrame] = None
    delta: DeltaList = field(default_factory=DeltaList)

    def clear(self):
        self.assignments = None
        self.data = None
        self.delta.clear()


class DeltaUpdateService(ErrorListMixin, UpdateService):
    deltaStarted = pyqtSignal("PyQt_PyObject")
    deltaStopped = pyqtSignal("PyQt_PyObject")

    paramsCls = DeltaUpdate

    def __init__(self, planManager: PlanManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._planManager = planManager
        self._deltas: dict[RdsPlan, DeltaUpdate] = {}
        self._planManager.planAdded.connect(self.planAdded)
        self._planManager.planRemoved.connect(self.planRemoved)
        self._commitSignals = QSignalMapper(self)
        self._commitSignals.mappedObject.connect(self.commitChanges)
        self._rollbackSignals = QSignalMapper(self)
        self._rollbackSignals.mappedObject.connect(self.rollback)
        self._assignmentChangedSignals = QSignalMapper(self)
        self._assignmentChangedSignals.mappedObject.connect(self.undoChanged)
        self.editingStartedSignals = QSignalMapper(self)
        self.editingStartedSignals.mappedObject.connect(self.watchPlan)
        self.editingStoppedSignals = QSignalMapper(self)
        self.editingStoppedSignals.mappedObject.connect(self.unwatchPlan)

    def planAdded(self, plan: RdsPlan):
        if plan.assignLayer:
            self.editingStartedSignals.setMapping(plan.assignLayer, plan)
            self.editingStoppedSignals.setMapping(plan.assignLayer, plan)
            plan.assignLayer.editingStarted.connect(self.editingStartedSignals.map)
            plan.assignLayer.editingStopped.connect(self.editingStoppedSignals.map)

    def planRemoved(self, plan: RdsPlan):
        if plan.assignLayer:
            plan.assignLayer.editingStarted.disconnect(self.editingStartedSignals.map)
            plan.assignLayer.editingStopped.disconnect(self.editingStoppedSignals.map)
            self.editingStartedSignals.removeMappings(plan.assignLayer)
            self.editingStoppedSignals.removeMappings(plan.assignLayer)

    def watchPlan(self, plan: RdsPlan):
        if plan not in self._deltas:
            delta = DeltaUpdate(plan)
            self._commitSignals.setMapping(plan.assignLayer, plan)
            self._rollbackSignals.setMapping(plan.assignLayer, plan)
            self._assignmentChangedSignals.setMapping(plan.assignLayer.undoStack(), plan)
            plan.assignLayer.afterCommitChanges.connect(self._commitSignals.map)
            plan.assignLayer.afterRollBack.connect(self._rollbackSignals.map)
            plan.assignLayer.undoStack().indexChanged.connect(self._assignmentChangedSignals.map)
            self._deltas[plan] = delta
            self.deltaStarted.emit(plan)

    def unwatchPlan(self, plan: RdsPlan):
        if plan in self._deltas:
            self.deltaStopped.emit(plan)
            plan.assignLayer.afterCommitChanges.disconnect(self._commitSignals.map)
            plan.assignLayer.afterRollBack.disconnect(self._rollbackSignals.map)
            plan.assignLayer.undoStack().indexChanged.disconnect(self._assignmentChangedSignals.map)
            self._commitSignals.removeMappings(plan.assignLayer)
            self._rollbackSignals.removeMappings(plan.assignLayer)
            self._assignmentChangedSignals.removeMappings(plan.assignLayer.undoStack())
            del self._deltas[plan]

    def _createParams(self, plan: "RdsPlan", *args, **kwargs):
        params = self._deltas.get(plan, None)
        if params is None:
            return None

        if (
            plan.assignLayer is None
            or plan.assignLayer.editBuffer() is None
            or plan.assignLayer.undoStack().index() == 0
        ):
            params.clear()
            return None

        return params

    def undoChanged(self, plan: RdsPlan):  # pylint: disable=unused-argument
        self.update(plan)

    def commitChanges(self, plan: RdsPlan):
        if plan in self._deltas:
            self._deltas[plan].clear()

    def rollback(self, plan: RdsPlan):
        if plan in self._deltas:
            self._deltas[plan].clear()

    def getDelta(self, plan: RdsPlan) -> DeltaList:
        if plan not in self._deltas:
            return None

        return self._deltas[plan].delta

    def loadPendingChanges(self, plan: RdsPlan):
        index = []
        data = []
        dindex = plan.assignLayer.fields().lookupField(plan.distField)
        if dindex == -1:
            raise ValueError(f"{plan.distField} not found in assignment layer")

        for k, v in plan.assignLayer.editBuffer().changedAttributeValues().items():
            if dindex in v:
                index.append(k)
                data.append(v[dindex])
        return pd.DataFrame({f"new_{plan.distField}": data}, index=index)

    def run(self, task: Optional[QgsTask], plan: RdsPlan, params: DeltaUpdate) -> UpdateParams:  # noqa: PLR0915
        feedback = IncrementalFeedback(task or QgsFeedback())

        feedback.setProgressIncrement(0, 10)
        df_new = self.loadPendingChanges(plan)
        feedback.checkCanceled()
        if df_new.empty:
            return params

        if params.assignments is None:
            feedback.setProgressIncrement(10, 30)
            with spatialite_connect(plan.geoPackagePath) as db:
                params.assignments = pd.read_sql(
                    f"SELECT fid, {quote_identifier(plan.geoIdField)}, "  # noqa: S608
                    f"{quote_identifier(plan.distField)} as {quote_identifier(f'old_{plan.distField}')} "
                    "FROM assignments",
                    db,
                    index_col="fid",
                )
            feedback.checkCanceled()

        if params.popData is None:
            feedback.setProgressIncrement(30, 70)
            params.popData = self._loadPopData(plan, feedback=feedback)
            feedback.checkCanceled()

        feedback.setProgressIncrement(70, 100)
        pending = params.assignments.join(df_new, how="inner")
        pending = pending[pending[f"new_{plan.distField}"] != pending[f"old_{plan.distField}"]]
        if len(pending) == 0:
            return params

        pending = pending.join(params.popData, on=plan.geoIdField, how="inner")
        feedback.setProgress(0.2)

        newdist = pending.drop(columns=f"old_{plan.distField}").groupby(f"new_{plan.distField}").sum(numeric_only=True)
        olddist = pending.drop(columns=f"new_{plan.distField}").groupby(f"old_{plan.distField}").sum(numeric_only=True)
        feedback.checkCanceled()

        data = newdist.sub(olddist, fill_value=0)
        dist = (
            params.assignments.join(params.popData, on=plan.geoIdField)
            .drop(columns=plan.geoIdField)
            .groupby(f"old_{plan.distField}")
            .sum()
        )
        feedback.setProgress(0.40)
        feedback.checkCanceled()
        dist = dist.loc[dist.index.intersection(data.index)]

        new = pd.DataFrame(0, index=data.index.difference(dist.index), columns=dist.columns)
        if len(new) > 0:
            dist = pd.concat([dist, new])
        members = [plan.districts.get(d).members for d in dist.index]
        dist["members"] = members

        data[f"new_{DistrictColumns.POPULATION}"] = dist[DistrictColumns.POPULATION] + data[DistrictColumns.POPULATION]
        data["deviation"] = data[f"new_{DistrictColumns.POPULATION}"] - (dist["members"] * plan.idealPopulation)
        data["pct_deviation"] = data["deviation"] / (dist["members"] * plan.idealPopulation)
        for fieldName in plan.popFields.keys():
            data[f"new_{fieldName}"] = dist[fieldName] + data[fieldName]
        for fieldName, fld in plan.dataFields.items():
            data[f"new_{fieldName}"] = dist[fieldName] + data[fieldName]
            pctbase = DistrictColumns.POPULATION if fld.pctBase == plan.popField else fld.pctBase
            if pctbase:
                data[f"pct_{fieldName}"] = data[f"new_{fieldName}"] / data[f"new_{pctbase}"]

        feedback.setProgress(0.8)
        feedback.checkCanceled()

        data["__name"] = pd.Series([plan.districts.get(i).name for i in data.index], data.index)

        cols = [f"new_{DistrictColumns.POPULATION}", DistrictColumns.POPULATION, "deviation", "pct_deviation"]
        for fieldName in plan.popFields.keys():
            cols.append(f"new_{fieldName}")
            cols.append(fieldName)
        for fieldName, fld in plan.dataFields.items():
            cols.append(f"new_{fieldName}")
            cols.append(fieldName)
            if fld.pctBase:
                cols.append(f"pct_{fieldName}")

        params.data = data.set_index("__name")[cols]
        feedback.setProgress(1.0)
        feedback.checkCanceled()

        return params

    def finished(
        self,
        status: UpdateService.UpdateStatus,
        task: Optional[QgsTask],
        plan: Optional[RdsPlan],
        params: Optional[DeltaUpdate],
        exception: Optional[Exception],
    ):
        if params is not None:
            if status == UpdateService.UpdateStatus.SUCCESS:
                params.delta.update(params.data)
            elif status == UpdateService.UpdateStatus.ERROR and exception is not None:
                self.setError(str(exception))
            params.task = None
            params.data = None

        return super().finished(status, task, plan, params, exception)
