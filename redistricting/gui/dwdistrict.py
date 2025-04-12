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
from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QWidget

from ..models import (
    RdsField,
    RdsPlan
)
from .dlgeditdatafields import DlgEditFields
from .rdsdockwidget import RdsDockWidget
from .ui.DistrictDataTable import Ui_qdwDistrictData


class DockDistrictDataTable(Ui_qdwDistrictData, RdsDockWidget):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.setupUi(self)
        self.helpContext = 'usage/data_table.html'
        self.fieldStats: dict[RdsField, QWidget] = {}

        self.lblWaiting.setParent(self.tblDataTable)

        self.btnAddFields.setIcon(
            QgsApplication.getThemeIcon('/mActionAddManualTable.svg'))
        self.btnAddFields.clicked.connect(self.addFieldDlg)

        self.btnHelp.setIcon(QgsApplication.getThemeIcon('/mActionHelpContents.svg'))
        self.btnHelp.clicked.connect(self.btnHelpClicked)

        self.btnDemographics.setIcon(QIcon(":/plugins/redistricting/demographics.svg"))
        self.btnMetrics.setIcon(QgsApplication.getThemeIcon('/mActionMeasureArea.svg'))

        self._plan: RdsPlan = None

    def addFieldDlg(self):
        dlg = DlgEditFields(self._plan)
        dlg.exec()
