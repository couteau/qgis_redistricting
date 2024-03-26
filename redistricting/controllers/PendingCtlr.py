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
from typing import Optional

from qgis.PyQt.QtCore import (
    QObject,
    Qt
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from ..gui import DockPendingChanges
from ..models import RedistrictingPlan
from ..utils import tr
from .BaseCtlr import BaseController


class PendingChangesController(BaseController):

    def __init__(
        self,
        iface,
        project,
        planManager,
        toolbar,
        parent: Optional[QObject] = None
    ):
        super().__init__(iface, project, planManager, toolbar, parent)
        self.dockwidget: DockPendingChanges = None
        self.actionToggle: QAction = None

    def load(self):
        self.setupPendingChangesWidget()
        self.planManager.activePlanChanged.connect(self.activePlanChanged)

    def unload(self):
        self.planManager.activePlanChanged.disconnect(self.activePlanChanged)
        self.iface.removeDockWidget(self.dockwidget)
        self.dockwidget.destroy()
        self.dockwidget = None

    def setupPendingChangesWidget(self):
        """Create the dockwidget with displays the impact of pending
        changes on affected districts."""
        dockwidget = DockPendingChanges(None)
        self.iface.addDockWidget(Qt.LeftDockWidgetArea, dockwidget)

        self.actionToggle = dockwidget.toggleViewAction()
        self.actionToggle.setIcon(QIcon(':/plugins/redistricting/preview.svg'))
        self.actionToggle.setText(tr('Pending Changes'))
        self.actionToggle.setStatusTip(tr('Show/hide pending changes dock widget'))
        self.toolbar.addAction(self.actionToggle)

        self.dockwidget = dockwidget
        return self.dockwidget

    def activePlanChanged(self, plan: RedistrictingPlan):
        self.dockwidget.plan = plan
