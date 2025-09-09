"""QGIS Redistricting Plugin - utilities for adding/copying/deleting districts

        begin                : 2024-09-15
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

import io
from typing import Optional
from uuid import UUID

import pandas as pd
from qgis.core import QgsApplication
from qgis.gui import QgisInterface, QgsMapMouseEvent, QgsMapToolIdentify
from qgis.PyQt.QtCore import QMimeData, QObject
from qgis.PyQt.QtGui import QAction
from qgis.PyQt.QtWidgets import QUndoCommand

from ..models import RdsDistrict, RdsPlan
from ..utils import LayerReader, tr
from .assignments import AssignmentsService
from .planmgr import PlanManager


class AddDistrictCommand(QUndoCommand):
    def __init__(self, plan: RdsPlan, district: int, name: str, members: int, description: str):
        super().__init__(tr("Add district '{}' to plan '{}'").format(name, plan.name))
        self._plan = plan
        self._district = district
        self._name = name
        self._members = members
        self._description = description

    def undo(self):
        self._plan.removeDistrict(self._district)

    def redo(self):
        if self._district in self._plan.districts.keys():
            return
        self._plan.addDistrict(self._district, self._name, self._members, self._description)


class RemoveDistrictCommand(QUndoCommand):
    def __init__(self, plan: RdsPlan, district: RdsDistrict):
        super().__init__(tr("remove district '{}' from plan '{}'").format(district.name, plan.name))
        self._plan = plan
        self._district = district

    def undo(self):
        self._plan.addDistrict(self._district)

    def redo(self):
        self._plan.removeDistrict(self._district)


class DistrictUtils(QObject):
    def __init__(
        self,
        iface: QgisInterface,
        planManager: PlanManager,
        assignmentsService: AssignmentsService,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.canvas = iface.mapCanvas()
        self.planManager = planManager
        self.assignmentsService = assignmentsService

    def canCopyOrCutAssignments(self, action: QAction, event: QgsMapMouseEvent):
        i = QgsMapToolIdentify(self.canvas)
        r = i.identify(event.x(), event.y(), layerList=[self.planManager.activePlan.distLayer])
        if r:
            f = r[0].mFeature
            if f[self.planManager.activePlan.distField] != 0:
                action.setData(f[self.planManager.activePlan.distField])
                return True

        return False

    def canPasteAssignments(self, plan: RdsPlan):
        if plan is None:
            plan = self.planManager.activePlan

        if plan is not None:
            cb = QgsApplication.instance().clipboard()
            if cb.mimeData().hasFormat("application/x-redist-planid") and cb.mimeData().hasFormat(
                "application/x-redist-assignments"
            ):
                planid = UUID(bytes=cb.mimeData().data("application/x-redist-planid").data())
                if planid != plan.id:
                    return True

        return False

    def getAssignments(self, district: int):
        s = LayerReader(self.planManager.activePlan.assignLayer)
        if district is not None:
            filt = {self.planManager.activePlan.distField: district}
        else:
            filt = None
        return s.read_layer(
            columns=["fid", self.planManager.activePlan.geoIdField, self.planManager.activePlan.distField],
            order="fid",
            filt=filt,
            read_geometry=False,
        )

    def copyDistrict(self, dist: Optional[int] = None):
        if dist is None or isinstance(dist, bool):
            action = self.sender()
            if isinstance(action, QAction):
                dist = action.data()
                if not isinstance(dist, int):
                    return
            else:
                return

        if dist not in self.planManager.activePlan.districts.keys():
            return

        cb = QgsApplication.instance().clipboard()
        assignments = self.getAssignments(dist).to_csv()
        mime = QMimeData()
        mime.setData("application/x-redist-planid", self.planManager.activePlan.id.bytes)
        mime.setData("application/x-redist-assignments", assignments.encode())
        mime.setText(assignments)
        cb.setMimeData(mime)

    def pasteDistrict(self):
        if not self.canPasteAssignments(self.planManager.activePlan):
            return

        cb = QgsApplication.instance().clipboard()
        assignments = pd.read_csv(io.StringIO(cb.mimeData().text()), index_col="fid")

        if not assignments.empty:
            planid = UUID(bytes=cb.mimeData().data("application/x-redist-planid").data())
            src_plan = self.planManager[planid]
            dest_plan = self.planManager.activePlan

            groups = assignments.groupby(src_plan.distField).groups

            assign = self.assignmentsService.getEditor(dest_plan)
            assign.beginEditCommand(tr("Paste district from {}").format(src_plan.name))

            for dist, fids in groups.items():
                # clear the current assignments for any districts that are being pasted
                assign.reassignDistrict(dist, 0)

                if dist not in dest_plan.districts.keys():
                    src_district = src_plan.districts.get(dist)
                    assign.pushUndoCommand(
                        AddDistrictCommand(
                            dest_plan, dist, src_district.name, src_district.members, src_district.description
                        )
                    )

                assign.assignFeaturesToDistrict(fids, dist)
            assign.endEditCommand()

    def deleteDistrict(self, dist: Optional[int] = None):
        if dist is None or isinstance(dist, bool):
            action = self.sender()
            if isinstance(action, QAction):
                dist = action.data()
                if not isinstance(dist, int):
                    return
            else:
                return

        plan = self.planManager.activePlan
        if dist not in plan.districts.keys():
            return

        # remove the assignments
        assign = self.assignmentsService.getEditor(plan)
        assign.beginEditCommand(tr("Delete district from {}").format(plan.name))
        assignments = self.getAssignments(dist)
        if not assignments.empty:
            assign.reassignDistrict(dist, 0)

        # remove the district
        assign.pushUndoCommand(RemoveDistrictCommand(plan, plan.districts.get(dist)))
        assign.endEditCommand()
