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

from ..models import RedistrictingPlan
from ..services import DeltaUpdateService
from .DeltaListModel import DeltaListModel
from .RdsOverlayWidget import OverlayWidget
from .ui.PendingChanges import Ui_qdwPendingChanges


class DockPendingChanges(Ui_qdwPendingChanges, QDockWidget):
    def __init__(self, deltaService: DeltaUpdateService, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.lblWaiting = OverlayWidget(self.tblPending)
        self.lblWaiting.setVisible(False)

        self._model = DeltaListModel(self)
        self.tblPending.setModel(self._model)
        self._plan = None

        self.deltaService = deltaService
        self.deltaService.updateStarted.connect(self.showOverlay)
        self.deltaService.updateCompleted.connect(self.hideOverlay)
        self.deltaService.updateTerminated.connect(self.hideOverlay)

    @property
    def plan(self) -> RedistrictingPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RedistrictingPlan):
        if self._plan != value:
            if self.lblWaiting.isVisible():
                self.lblWaiting.stop()
            self._plan = value
            self._model.setPlan(value)
            if self.deltaService.isUpdating(self._plan):
                self.lblWaiting.start()

    def showOverlay(self, plan: RedistrictingPlan):
        if plan == self._plan:
            self.lblWaiting.start()

    def hideOverlay(self, plan):
        if plan == self._plan:
            self.lblWaiting.stop()
