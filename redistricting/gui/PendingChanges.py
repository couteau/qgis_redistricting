# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - QDockWidget showing pending district changes

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
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import (
    QAbstractItemModel,
    QTransposeProxyModel
)
from qgis.PyQt.QtGui import QIcon

from .RdsDockWidget import RdsDockWidget
from .ui.PendingChanges import Ui_qdwPendingChanges


class DockPendingChanges(Ui_qdwPendingChanges, RdsDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.lblWaiting.setParent(self.tblPending)

        self._model = QTransposeProxyModel(self)
        self.tblPending.setModel(self._model)

        self.helpContext = 'usage/preview.html'
        self.btnHelp.setIcon(QgsApplication.getThemeIcon('/mActionHelpContents.svg'))
        self.btnHelp.clicked.connect(self.btnHelpClicked)

        self.btnDemographics.setIcon(QIcon(":/plugins/redistricting/demographics.svg"))

    def model(self):
        return self._model.sourceModel()

    def setModel(self, model: QAbstractItemModel):
        self._model.setSourceModel(model)
