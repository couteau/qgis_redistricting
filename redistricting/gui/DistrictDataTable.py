# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - A QDockWidget that shows selected demographic
        data for the active Redistricting Plan

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
from typing import Optional

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QObject
)
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget
)

from ..models import (
    RdsField,
    RdsPlan
)
from .DlgEditFields import DlgEditFields
from .help import showHelp
from .RdsOverlayWidget import OverlayWidget
from .ui.DistrictDataTable import Ui_qdwDistrictData


class DockDistrictDataTable(Ui_qdwDistrictData, QDockWidget):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.setupUi(self)

        self.fieldStats: dict[RdsField, QWidget] = {}

        self.tblDataTable.installEventFilter(self)
        self.lblWaiting = OverlayWidget(self.tblDataTable)
        self.lblWaiting.setVisible(False)

        self.tblPlanMetrics.verticalHeader()
        self.gbxPlanMetrics.setContentsMargins(0, 20, 0, 0)

        self.btnAddFields.setIcon(
            QgsApplication.getThemeIcon('/mActionAddManualTable.svg'))
        self.btnAddFields.clicked.connect(self.addFieldDlg)

        self.btnHelp.setIcon(QgsApplication.getThemeIcon('/mActionHelpContents.svg'))
        self.btnHelp.clicked.connect(self.btnHelpClicked)

        self._plan: RdsPlan = None

    @property
    def plan(self) -> RdsPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RdsPlan):
        if self._plan is not None:
            self._plan.nameChanged.disconnect(self.planNameChanged)

        self.gbxPlanMetrics.setContentsMargins(0, 20, 0, 0)
        self._plan = value

        if self._plan is None:
            self.btnAddFields.setEnabled(False)
            self.lblPlanName.setText(QCoreApplication.translate('Redistricting', 'No plan selected'))
        else:
            self._plan.nameChanged.connect(self.planNameChanged)
            self.btnAddFields.setEnabled(True)
            self.lblPlanName.setText(self._plan.name)

    def planNameChanged(self, name):
        self.lblPlanName.setText(name)

    def addFieldDlg(self):
        dlg = DlgEditFields(self._plan)
        dlg.exec_()

    def btnHelpClicked(self):
        showHelp('usage/data_table.html')

    def setWaiting(self, on: bool = True):
        if on and not self.lblWaiting.isVisible():
            self.lblWaiting.start()
        elif self.lblWaiting.isVisible():
            self.lblWaiting.stop()
