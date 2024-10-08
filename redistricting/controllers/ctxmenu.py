"""QGIS Redistricting Plugin - controller for context menu actions

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
from typing import (
    TYPE_CHECKING,
    Optional
)
from uuid import UUID

from qgis.core import (
    QgsMapLayer,
    QgsMapLayerType,
    QgsProject
)
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QMenu,
    QToolBar
)

from ..models import RdsPlan
from ..services import PlanManager
from ..utils import tr
from .base import BaseController
from .plan import PlanController

if TYPE_CHECKING:
    from PyQt5.QtWidgets import QAction
else:
    from qgis.PyQt.QtWidgets import QAction


class ContextMenuController(BaseController):
    def __init__(
        self,
        iface: QgisInterface,
        project: QgsProject,
        planManager: PlanManager,
        toolbar: QToolBar,
        planController: PlanController,
        parent: Optional[QObject] = None
    ):
        super().__init__(iface, project, planManager, toolbar, parent)

        self.contextAction = QAction(
            QIcon(':/plugins/redistricting/icon.png'),
            self.tr('Redistricting'),
            self.iface.mainWindow()
        )

        self.contextMenu = QMenu(self.tr('Redistricting Plan'), self.iface.mainWindow())
        action = QAction(
            QIcon(':/plugins/redistricting/activateplan.svg'),
            tr('Activate Plan'),
            self.iface.mainWindow()
        )
        action.triggered.connect(self.contextMenuActivatePlan)
        self.contextMenu.addAction(action)

        action = QAction(
            QIcon(':/plugins/redistricting/editplan.svg'),
            tr('Edit Plan'),
            self.iface.mainWindow()
        )
        action.triggered.connect(self.contextMenuSlot(planController.editPlan))
        self.contextMenu.addAction(action)

        action = QAction(
            QIcon(':/plugins/redistricting/exportplan.svg'),
            tr('Export Plan'),
            self.iface.mainWindow()
        )
        action.triggered.connect(self.contextMenuSlot(planController.exportPlan))
        self.contextMenu.addAction(action)

        self.contextAction.setMenu(self.contextMenu)

    def load(self):
        self.iface.addCustomActionForLayerType(self.contextAction, None, QgsMapLayerType.GroupLayer, False)
        self.iface.addCustomActionForLayerType(self.contextAction, None, QgsMapLayerType.VectorLayer, False)
        self.iface.layerTreeView().clicked.connect(self.layerChangedActivatePlan)

    def unload(self):
        self.iface.layerTreeView().clicked.disconnect(self.layerChangedActivatePlan)
        self.iface.removeCustomActionForLayerType(self.contextAction)

    def layerChangedActivatePlan(self, layer: QgsMapLayer):  # pylint: disable=unused-argument
        g = self.iface.layerTreeView().currentGroupNode()
        if g.isVisible():
            p = g.customProperty('redistricting-plan-id', None)
            if p is not None and (self.planManager.activePlan is None or p != str(self.planManager.activePlan.id)):
                self.planManager.setActivePlan(UUID(p))
                self.project.setDirty()

    def contextMenuActivatePlan(self):
        group = self.iface.layerTreeView().currentGroupNode()
        planid = group.customProperty('redistricting-plan-id', None)
        if planid and planid != self.planManager.activePlan.id:
            self.planManager.setActivePlan(planid)
            self.project.setDirty()

    def planAdded(self, plan: RdsPlan):
        self.iface.addCustomActionForLayer(self.contextAction, plan.assignLayer)
        self.iface.addCustomActionForLayer(self.contextAction, plan.distLayer)

    def contextMenuSlot(self, action):
        def trigger():
            group = self.iface.layerTreeView().currentGroupNode()
            planid = group.customProperty('redistricting-plan-id', None)
            plan = self.planManager.get(planid)
            if plan:
                action(plan)

        return trigger
