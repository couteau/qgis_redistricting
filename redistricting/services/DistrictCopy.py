
import io
from typing import Optional
from uuid import UUID

import pandas as pd
from qgis.core import QgsApplication
from qgis.gui import (
    QgisInterface,
    QgsMapMouseEvent,
    QgsMapToolIdentify
)
from qgis.PyQt.QtCore import (
    QMimeData,
    QObject
)
from qgis.PyQt.QtWidgets import QAction

from ..models import RedistrictingPlan
from ..utils import (
    LayerReader,
    tr
)
from .actions import ActionRegistry
from .PlanAssignments import AssignmentsService
from .PlanManager import PlanManager


class DistrictCopier(QObject):
    def __init__(self, iface: QgisInterface, planManager: PlanManager, assignmentsService: AssignmentsService, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.canvas = iface.mapCanvas()
        self.planManager = planManager
        self.assignmentsService = assignmentsService

        actions = ActionRegistry()

        self.actionCopyDistrict = actions.createAction(
            name='actionCopyDistrict',
            icon=':/plugins/redistricting/copydistrict.svg',
            text=str('Copy District'),
            tooltip=tr('Copy district to clipboard'),
            callback=self.copyDistrict,
            parent=iface.mainWindow()
        )

        self.actionPasteDistrict = actions.createAction(
            name='actionPasteDistrict',
            icon=QgsApplication.getThemeIcon('/mActionDuplicateFeature.svg'),
            text=tr('Paste District'),
            tooltip=tr('Paste district from clipboard'),
            callback=self.pasteDistrict,
            parent=iface.mainWindow()
        )

        self.actionZoomToDistrict = actions.createAction(
            name="actionZoomToDistrict",
            icon=':/plugins/redistricting/zoomdistrict.svg',
            text=tr("Zoom to district"),
            callback=self.zoomToDistrict,
            parent=iface.mainWindow()
        )

        self.actionFlashDistrict = actions.createAction(
            name='actionFlashDistrict',
            icon=':/plugins/redistricting/flashdistrict.svg',
            text=self.tr("Flash district"),
            callback=self.flashDistrict,
            parent=iface.mainWindow()
        )

    def canCopyAssignments(self, action: QAction, event: QgsMapMouseEvent):
        i = QgsMapToolIdentify(self.canvas)
        r = i.identify(event.x(), event.y(), layerList=[self.planManager.activePlan.distLayer])
        if r:
            f = r[0].mFeature
            if f[self.planManager.activePlan.distField] != 0:
                action.setData(f[self.planManager.activePlan.distField])
                return True

        return False

    def canPasteAssignments(self, plan: RedistrictingPlan):
        if plan is None:
            plan = self.planManager.activePlan

        if plan is not None:
            cb = QgsApplication.instance().clipboard()
            if cb.mimeData().hasFormat('application/x-redist-planid') and cb.mimeData().hasFormat('application/x-redist-assignments'):
                planid = UUID(bytes=cb.mimeData().data('application/x-redist-planid').data())
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
            ['fid', self.planManager.activePlan.geoIdField, self.planManager.activePlan.distField],
            order='fid',
            filt=filt,
            read_geometry=False
        ).to_csv()

    def copyDistrict(self, dist: Optional[int] = None):
        if dist is None or isinstance(dist, bool):
            action = self.sender()
            if isinstance(action, QAction):
                dist = action.data()
            else:
                return

        cb = QgsApplication.instance().clipboard()
        assignments = self.getAssignments(dist)
        mime = QMimeData()
        mime.setData('application/x-redist-planid', self.planManager.activePlan.id.bytes)
        mime.setData('application/x-redist-assignments', assignments.encode())
        mime.setText(assignments)
        cb.setMimeData(mime)

    def pasteDistrict(self):
        if not self.canPasteAssignments(self.planManager.activePlan):
            return

        cb = QgsApplication.instance().clipboard()
        assignments = pd.read_csv(io.StringIO(cb.mimeData().text()), index_col="fid")

        if not assignments.empty:
            groups = assignments.groupby(self.planManager.activePlan.distField).groups

            assign = self.assignmentsService.getEditor(self.planManager.activePlan)
            assign.startEditCommand(tr('Paste district'))

            # clear the current assignments for any districts that are being pasted
            for d in groups.keys():
                assign.reassignDistrict(d, 0)

            assign.changeAssignments(groups)
            assign.endEditCommand()

    def zoomToDistrict(self, district: Optional[int]):
        if self.planManager.activePlan is None:
            return

        if district is None:
            action = self.sender()
            if isinstance(action, QAction):
                district = action.data()

        if not (isinstance(district, int) and 1 <= district <= self.planManager.activePlan.numDistricts):
            return

        fid = self.planManager.activePlan.districts[district].fid
        if fid is not None:
            self.canvas.zoomToFeatureIds(self.planManager.activePlan.distLayer, [fid])
            self.canvas.refresh()

    def flashDistrict(self, district: Optional[int]):
        if self.planManager.activePlan is None:
            return

        if district is None:
            action = self.sender()
            if isinstance(action, QAction):
                district = action.data()

        if not (isinstance(district, int) and 1 <= district <= self.planManager.activePlan.numDistricts):
            return

        fid = self.planManager.activePlan.districts[district].fid
        if fid is not None:
            self.canvas.flashFeatureIds(self.planManager.activePlan.distLayer, [fid])
