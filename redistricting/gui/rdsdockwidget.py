# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - Custom QgsDockWidget with plan property

        begin                : 2024-09-20
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
from qgis.gui import QgsDockWidget
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QLabel

from ..models import RdsPlan
from ..utils import tr
from .help import showHelp
from .rdsoverlaywidget import OverlayWidget


class RdsDockWidget(QgsDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lblPlanName: QLabel = None
        self._plan: RdsPlan = None
        self.lblWaiting = OverlayWidget()
        self.lblWaiting.setVisible(False)
        self.helpContext: str = 'index.html'
        self.dockLocationChanged.connect(self.dockChanged)

    @property
    def plan(self) -> RdsPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RdsPlan):
        if self._plan is not None and self.lblPlanName is not None:
            self._plan.nameChanged.disconnect(self.planNameChanged)

        self._plan = value

        if self.lblPlanName is not None:
            if self._plan is None:
                self.lblPlanName.setText(tr('No plan selected'))
            else:
                self._plan.nameChanged.connect(self.planNameChanged)
                self.lblPlanName.setText(self._plan.name)

    def planNameChanged(self, name):
        self.lblPlanName.setText(name)

    def btnHelpClicked(self):
        showHelp(self.helpContext)

    def setWaiting(self, on: bool = True):
        if self.lblWaiting.parent() is None:
            return

        if on:
            self.lblWaiting.start()
        else:
            self.lblWaiting.stop()

    def dockChanged(self, area: Qt.DockWidgetArea):
        if area == Qt.NoDockWidgetArea:
            self.layout().setContentsMargins(8, 4, 8, 4)
        else:
            self.layout().setContentsMargins(0, 4, 0, 4)
