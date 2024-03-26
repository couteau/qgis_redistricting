"""QGIS Redistricting Plugin - district-related actions

        begin                : 2024-03-20
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
from pytest_qgis import QgsProject
from qgis.core import QgsApplication
from qgis.gui import (
    QgisInterface,
    QgsMapMouseEvent,
    QgsMapToolIdentify
)
from qgis.PyQt.QtCore import (
    QMimeData,
    QObject,
    Qt
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QMenu,
    QToolBar
)

from ..gui import DockDistrictDataTable
from ..models import RedistrictingPlan
from ..services import (
    AssignmentsService,
    PlanManager
)
from ..utils import (
    LayerReader,
    tr
)
from .BaseCtlr import BaseController


class DistrictController(BaseController):
    def __init__(
        self,
        iface: QgisInterface,
        project: QgsProject,
        planManager: PlanManager,
        toolbar: QToolBar,
        assignmentsService: AssignmentsService,
        parent: Optional[QObject] = None
    ):
        super().__init__(iface, project, planManager, toolbar, parent)
        self.canvas = iface.mapCanvas()
        self.assignmentsService = assignmentsService
        self.actionToggle: QAction = None
        self.dockwidget: DockDistrictDataTable = None
        self.actionCopyDistrict = QAction(
            icon=QIcon(':/plugins/redistricting/copydistrict.svg'),
            text=str('Copy district'),
            parent=self.iface.mainWindow()
        )
        self.actionCopyDistrict.setToolTip(tr('Copy district to clipboard'))
        self.actionCopyDistrict.triggered.connect(self.copyDistrict)

        self.actionPasteDistrict = QAction(
            icon=QgsApplication.getThemeIcon('/mActionDuplicateFeature.svg'),
            text=tr('Paste district'),
            parent=self.iface.mainWindow()
        )
        self.actionPasteDistrict.setToolTip(tr('Paste district from clipboard'))
        self.actionPasteDistrict.triggered.connect(self.pasteDistrict)

        self.actionZoomToDistrict = QAction(
            icon=QIcon(':/plugins/redistricting/zoomdistrict.svg'),
            text=self.tr("Zoom to district"),
            parent=self.iface.mainWindow()
        )
        self.actionZoomToDistrict.triggered.connect(self.zoomToDistrict)

        self.actionFlashDistrict = QAction(
            icon=QIcon(':/plugins/redistricting/flashdistrict.svg'),
            text=self.tr("Flash district"),
            parent=self.iface.mainWindow()
        )
        self.actionFlashDistrict.triggered.connect(self.flashDistrict)

    def load(self):
        self.createDataTableDockWidget()
        self.planManager.activePlanChanged.connect(self.activePlanChanged)
        self.canvas.contextMenuAboutToShow.connect(self.addCanvasContextMenuItems)

    def unload(self):
        self.canvas.contextMenuAboutToShow.disconnect(self.addCanvasContextMenuItems)
        self.planManager.activePlanChanged.disconnect(self.activePlanChanged)
        self.iface.removeDockWidget(self.dockwidget)
        self.dockwidget.destroy()
        self.dockwidget = None

    def createDataTableDockWidget(self):
        """Create the dockwidget that displays district statistics."""
        dockwidget = DockDistrictDataTable(None, self)
        self.iface.addDockWidget(Qt.BottomDockWidgetArea, dockwidget)

        self.actionToggle = dockwidget.toggleViewAction()
        self.actionToggle.setIcon(QgsApplication.getThemeIcon('/mActionOpenTable.svg'))
        self.actionToggle.setText(tr('District Data'))
        self.actionToggle.setStatusTip(tr('Show/hide district demographic data/metrics table'))
        self.toolbar.addAction(self.actionToggle)

        self.dockwidget = dockwidget
        return self.dockwidget

    def activePlanChanged(self, plan):
        self.dockwidget.plan = plan

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

    def canCopyAssignments(self, event: QgsMapMouseEvent):
        i = QgsMapToolIdentify(self.canvas)
        r = i.identify(event.x(), event.y(), layerList=[self.planManager.activePlan.distLayer])
        if r:
            f = r[0].mFeature
            if f[self.planManager.activePlan.distField] != 0:
                self.actionCopyDistrict.setData(f[self.planManager.activePlan.distField])
                return True

        return False

    def canPasteAssignments(self, plan: RedistrictingPlan):
        if self.planManager.activePlan is not None:
            cb = QgsApplication.instance().clipboard()
            if cb.mimeData().hasFormat('application/x-redist-planid') \
                    and cb.mimeData().hasFormat('application/x-redist-assignments'):
                planid = UUID(bytes=cb.mimeData().data('application/x-redist-planid').data())
                if planid != plan.id:
                    return True

        return False

    def copyDistrict(self):
        cb = QgsApplication.instance().clipboard()
        dist: int = self.actionCopyDistrict.data()
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
            assign = self.assignmentsService.startEditing(self.planManager.activePlan)
            assign.startEditCommand(tr('Paste district'))
            assign.changeAssignments(
                assignments.groupby(self.planManager.activePlan.distField).groups
            )
            assign.endEditCommand()

    def addCanvasContextMenuItems(self, menu: QMenu, event: QgsMapMouseEvent):
        menu.addAction(self.actionCopyDistrict)
        self.actionCopyDistrict.setEnabled(self.canCopyAssignments(event))

        menu.addAction(self.actionPasteDistrict)
        self.actionPasteDistrict.setEnabled(self.canPasteAssignments(self.planManager.activePlan))

    def zoomToDistrict(self):
        if self.planManager.activePlan is None:
            return

        district = self.actionZoomToDistrict.data()
        if not (isinstance(district, int) and 1 <= district <= self.planManager.activePlan.numDistricts):
            return

        fid = self.planManager.activePlan.districts[district]["fid"]
        if fid is not None:
            self.iface.mapCanvas().zoomToFeatureIds(self.planManager.activePlan.distLayer, [fid])
            self.iface.mapCanvas().refresh()

    def flashDistrict(self):
        if self.planManager.activePlan is None:
            return

        district = self.actionZoomToDistrict.data()

        if not (isinstance(district, int) and 1 <= district <= self.planManager.activePlan.numDistricts):
            return
        fid = self.planManager.activePlan.districts[district]["fid"]
        if fid is not None:
            self.canvas.flashFeatureIds(self.planManager.activePlan.distLayer, [fid])
