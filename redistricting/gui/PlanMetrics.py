# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - QDockWidget displaying plan metrics

        begin                : 2024-09-20
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
from qgis.core import QgsApplication

from .RdsDockWidget import RdsDockWidget
from .ui.PlanMetrics import Ui_qdwPlanMetrics


class DockPlanMetrics(Ui_qdwPlanMetrics, RdsDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.lblWaiting.setParent(self.tblPlanMetrics)
        self.btnHelp.setIcon(QgsApplication.getThemeIcon('/mActionHelpContents.svg'))
        self.btnHelp.clicked.connect(self.btnHelpClicked)
