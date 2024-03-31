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
from typing import Optional

from pytest_qgis import QgsProject
from qgis.core import QgsApplication
from qgis.gui import (
    QgisInterface,
    QgsMapMouseEvent
)
from qgis.PyQt.QtCore import (
    QObject,
    Qt
)
from qgis.PyQt.QtWidgets import (
    QAction,
    QMenu,
    QToolBar
)

from ..gui import DockDistrictDataTable
from ..services import (
    ActionRegistry,
    AssignmentsService,
    DistrictCopier,
    DistrictUpdater,
    PlanManager
)
from ..utils import tr
from .BaseCtlr import BaseController


class DistrictController(BaseController):
    def __init__(
        self,
        iface: QgisInterface,
        project: QgsProject,
        planManager: PlanManager,
        toolbar: QToolBar,
        assignmentsService: AssignmentsService,
        districtCopier: DistrictCopier,
        updateService: DistrictUpdater,
        parent: Optional[QObject] = None
    ):
        super().__init__(iface, project, planManager, toolbar, parent)
        self.canvas = iface.mapCanvas()
        self.assignmentsService = assignmentsService
        self.districtCopier = districtCopier
        self.updateService = updateService
        self.actionToggle: QAction = None
        self.dockwidget: DockDistrictDataTable = None
        self.actions = ActionRegistry()

        self.actionCopyDistrict = self.actions.actionCopyDistrict
        self.actionPasteDistrict = self.actions.actionPasteDistrict
        self.actionZoomToDistrict = self.actions.actionZoomToDistrict
        self.actionFlashDistrict = self.actions.actionFlashDistrict

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
        dockwidget = DockDistrictDataTable(self.updateService, self.districtCopier)
        self.iface.addDockWidget(Qt.BottomDockWidgetArea, dockwidget)

        self.actionToggle = dockwidget.toggleViewAction()
        self.actionToggle.setIcon(QgsApplication.getThemeIcon('/mActionOpenTable.svg'))
        self.actionToggle.setText(tr('District Data'))
        self.actionToggle.setStatusTip(tr('Show/hide district demographic data/metrics table'))
        self.actions.registerAction('actionToggleDataTable', self.actionToggle)
        self.toolbar.addAction(self.actionToggle)

        self.dockwidget = dockwidget
        return self.dockwidget

    def activePlanChanged(self, plan):
        self.dockwidget.plan = plan

    def addCanvasContextMenuItems(self, menu: QMenu, event: QgsMapMouseEvent):
        menu.addAction(self.actionCopyDistrict)
        self.actionCopyDistrict.setEnabled(self.districtCopier.canCopyAssignments(self.actionCopyDistrict, event))

        menu.addAction(self.actionPasteDistrict)
        self.actionPasteDistrict.setEnabled(self.districtCopier.canPasteAssignments(self.planManager.activePlan))
