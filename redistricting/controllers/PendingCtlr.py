"""QGIS Redistricting Plugin - actions for displaying pending changes

        begin                : 2024-03-23
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
    Optional,
    Union
)

from qgis.PyQt.QtCore import (
    QObject,
    Qt,
    QTransposeProxyModel
)
from qgis.PyQt.QtGui import QIcon

from ..gui import DockPendingChanges
from ..models import (
    DeltaList,
    RdsPlan
)
from ..services import (
    DeltaListModel,
    DeltaUpdateService,
    PlanManager
)
from ..utils import tr
from .BaseCtlr import BaseController

if TYPE_CHECKING:
    from PyQt5.QtWidgets import QAction
else:
    from qgis.PyQt.QtWidgets import QAction


class PendingChangesController(BaseController):
    def __init__(
        self,
        iface,
        project,
        planManager: PlanManager,
        toolbar,
        deltaService: DeltaUpdateService,
        parent: Optional[QObject] = None
    ):
        super().__init__(iface, project, planManager, toolbar, parent)
        self.deltaService = deltaService
        self.dockwidget: DockPendingChanges = None
        self.actionToggle: QAction = None
        self.model: DeltaListModel = DeltaListModel(self.iface)
        self.proxyModel = QTransposeProxyModel(self.iface)
        self.proxyModel.setSourceModel(self.model)
        self.deltaService.updateCompleted.connect(self.updateDelta)

    def load(self):
        self.setupPendingChangesWidget()
        self.planManager.activePlanChanged.connect(self.activePlanChanged)
        self.deltaService.updateStarted.connect(self.showOverlay)
        self.deltaService.updateCompleted.connect(self.hideOverlay)
        self.deltaService.updateTerminated.connect(self.hideOverlay)

    def unload(self):
        self.deltaService.updateStarted.disconnect(self.showOverlay)
        self.deltaService.updateCompleted.disconnect(self.hideOverlay)
        self.deltaService.updateTerminated.disconnect(self.hideOverlay)
        self.planManager.activePlanChanged.disconnect(self.activePlanChanged)
        self.iface.removeDockWidget(self.dockwidget)
        self.dockwidget.destroy()
        self.dockwidget = None

    def setupPendingChangesWidget(self):
        """Create the dockwidget with displays the impact of pending
        changes on affected districts."""
        dockwidget = DockPendingChanges()
        dockwidget.tblPending.setModel(self.proxyModel)

        self.iface.addDockWidget(Qt.LeftDockWidgetArea, dockwidget)

        self.actionToggle = dockwidget.toggleViewAction()
        self.actionToggle.setIcon(QIcon(':/plugins/redistricting/preview.svg'))
        self.actionToggle.setText(tr('Pending Changes'))
        self.actionToggle.setStatusTip(tr('Show/hide pending changes dock widget'))
        self.toolbar.addAction(self.actionToggle)

        self.dockwidget = dockwidget
        return self.dockwidget

    def activePlanChanged(self, plan: Union[RdsPlan, None]):
        self.dockwidget.setWaiting(False)
        self.dockwidget.plan = plan
        if plan is None:
            self.model.setDelta(None, None)
        else:
            self.model.setDelta(plan, self.deltaService.getDelta(plan))
            if self.deltaService.isUpdating(plan):
                self.dockwidget.setWaiting(True)

    def updateDelta(self, plan, delta: DeltaList):
        if plan == self.activePlan:
            self.model.setDelta(plan, delta)

    def showOverlay(self, plan: RdsPlan):
        if plan == self.activePlan:
            self.dockwidget.setWaiting(True)

    def hideOverlay(self, plan: RdsPlan):
        if plan == self.activePlan:
            self.dockwidget.setWaiting(False)
