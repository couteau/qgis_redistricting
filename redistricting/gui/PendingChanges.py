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
from .ui.PendingChanges import Ui_qdwPendingChanges
from .RdsOverlayWidget import OverlayWidget
from ..core import RedistrictingPlan, DeltaListModel


class DockPendingChanges(Ui_qdwPendingChanges, QDockWidget):

    _plan: RedistrictingPlan = None

    @property
    def plan(self) -> RedistrictingPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RedistrictingPlan):
        self._plan = value
        self._model.setPlan(value)
        if not value and self.lblWaiting.isVisible():
            self.lblWaiting.stop()

    def __init__(self, plan, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.lblWaiting = OverlayWidget(self.tblPending)
        self.lblWaiting.setVisible(False)

        self._model = DeltaListModel(None, self)
        self.tblPending.setModel(self._model)
        self.plan = plan

        self._model.modelAboutToBeReset.connect(self.showOverlay)
        self._model.modelReset.connect(self.hideOverlay)

    def showOverlay(self):
        self.lblWaiting.start()

    def hideOverlay(self):
        self.lblWaiting.stop()
