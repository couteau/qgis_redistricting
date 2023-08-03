# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - Edit Data Fields dialog
                              -------------------
        begin                : 2022-06-07
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

from ..core import RedistrictingPlan
from ._dlgEditPlanFieldPage import dlgEditPlanFieldPage


class DlgEditFields(QDialog):
    def __init__(
        self,
        plan: RedistrictingPlan,
        parent: Optional[QWidget] = None,
        flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.Dialog
    ):
        super().__init__(parent, flags)
        self.plan = plan
        self.page = dlgEditPlanFieldPage(self)
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.page.setField('dataFields', plan.dataFields)

        layout = QVBoxLayout(self)
        layout.addWidget(self.page)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)
        self.setBaseSize(446, 510)

        self.page.initializePage()
        self.page.fexDataField.setLayer(plan.popLayer or plan.geoLayer)

    def accept(self):
        self.plan.dataFields = self.page.field('dataFields')
        super().accept()
