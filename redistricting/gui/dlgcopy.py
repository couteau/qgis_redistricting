# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - Copy Plan Dialog

        begin                : 2022-03-18
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
import os
import re
from typing import (
    Optional,
    Union
)

from qgis.core import QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QWidget
)

from ..models import RdsPlan
from ..utils import tr
from .ui.DlgCopyPlan import Ui_dlgCopyPlan


class DlgCopyPlan(Ui_dlgCopyPlan, QDialog):
    def __init__(self, plan: RdsPlan, parent: Optional[QWidget] = None, flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.WindowType.Dialog):
        super().__init__(parent, flags)
        self.setupUi(self)

        self.setTabOrder(self.inpPlanName, self.fwGeoPackage.lineEdit())

        self.lblSourcePlan.setText(tr('Copy from <b>{plan}</b>').format(plan=plan.name))
        self.cbxCopyAssignments.setText(tr('Copy {geography} assignments').format(geography=plan.geoIdCaption.lower()))
        self.inpPlanName.editingFinished.connect(self.planNameChanged)
        self.inpPlanName.textChanged.connect(self.updateButtonBox)
        self.txtDescription.setPlainText(plan.description)
        self.fwGeoPackage.fileChanged.connect(self.updateButtonBox)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    @property
    def planName(self) -> str:
        return self.inpPlanName.text()

    @property
    def geoPackagePath(self) -> str:
        return self.fwGeoPackage.filePath()

    @property
    def copyAssignments(self) -> bool:
        return self.cbxCopyAssignments.isChecked()

    @property
    def description(self) -> str:
        return self.txtDescription.toPlainText()

    def planNameChanged(self):
        if self.planName and not self.fwGeoPackage.path and QgsProject.instance().absolutePath() != ' ':
            self.fwGeoPackage.setFilePath(
                os.path.join(
                    QgsProject.instance().absolutePath(),
                    re.sub(r'[^\w]+', '_', self.planName) + '.gpkg'
                )
            )

    def updateButtonBox(self):
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            bool(self.planName) and bool(self.fwGeoPackage.filePath())
        )
