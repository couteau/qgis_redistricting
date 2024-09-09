# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - QDockWidget showing pending district changes

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
from qgis.PyQt.QtWidgets import QDockWidget

from ..models import RdsPlan
from .RdsOverlayWidget import OverlayWidget
from .ui.PendingChanges import Ui_qdwPendingChanges


class DockPendingChanges(Ui_qdwPendingChanges, QDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.lblWaiting = OverlayWidget(self.tblPending)
        self.lblWaiting.setVisible(False)

        self._plan: RdsPlan = None

    @property
    def plan(self) -> RdsPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RdsPlan):
        if self._plan != value:
            self._plan = value

    def setWaiting(self, on: bool = True):
        if on and not self.lblWaiting.isVisible():
            self.lblWaiting.start()
        elif self.lblWaiting.isVisible():
            self.lblWaiting.stop()
