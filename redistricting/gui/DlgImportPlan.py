# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - Import Assignments Dialog

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
from typing import (
    Optional,
    Union
)

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QWidget
)

from ..models import RdsPlan
from ..utils import tr
from ._dlgEditPlanImportPage import dlgEditPlanImportPage


class DlgImportPlan(QDialog):
    def __init__(self, plan: RdsPlan, parent: Optional[QWidget] = None, flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.Dialog):
        super().__init__(parent, flags)
        self.setWindowTitle(tr("Import Equivalency File"))
        self.page = dlgEditPlanImportPage(self)
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.page.fileImportFrom.fileChanged.connect(self.updateButton)

        layout = QVBoxLayout(self)
        layout.addWidget(self.page)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)

        self.page.initializePage()
        self.page.cmbJoinField.setLayer(plan.assignLayer)
        self.page.cmbJoinField.setField(plan.geoIdField)

    def updateButton(self):
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(
            bool(self.equivalencyFileName)
        )

    @property
    def headerRow(self):
        return self.page.headerRow

    @property
    def equivalencyFileName(self):
        return self.page.importPath

    @property
    def joinField(self):
        return self.page.joinField

    @property
    def geoColumn(self):
        return self.page.geoColumn

    @property
    def distColumn(self):
        return self.page.distColumn

    @property
    def delimiter(self):
        return self.page.delimiter

    @property
    def quotechar(self):
        return self.page.quotechar
