"""QGIS Redistricting Plugin - New/Edit Plan Wizard - Details Page

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

import os
import re

from qgis.core import QgsProject
from qgis.PyQt.QtWidgets import QWizardPage

from .ui.WzpEditPlanDetailsPage import Ui_wzpPlanDetails


class dlgEditPlanDetailsPage(Ui_wzpPlanDetails, QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.registerField("planName*", self.inpPlanName)
        self.registerField("gpkgPath*", self.fileGpkg, "path", self.fileGpkg.fileChanged)
        self.registerField("description", self.txtDescription, "plainText", self.txtDescription.textChanged)
        self.registerField("numDistricts", self.sbxNumDistricts)
        self.registerField("numSeats", self.sbxNumSeats)

        self.inpPlanName.editingFinished.connect(self.planNameChanged)
        self.setTabOrder(self.inpPlanName, self.fileGpkg.lineEdit())
        self.sbxNumDistricts.valueChanged.connect(self.numDistrictsChanged)
        self.sbxNumSeats.valueChanged.connect(self.numSeatsChanged)
        self.linkSeats = True

    def initializePage(self):
        super().initializePage()
        self.linkSeats = self.field("numDistricts") == self.field("numSeats")
        self.inpPlanName.setFocus()
        if not self.wizard().new and self.fileGpkg.filePath():
            self.fileGpkg.setEnabled(False)
        self.setFinalPage(self.wizard().isComplete())

    def planNameChanged(self):
        if self.inpPlanName.text() and not self.fileGpkg.path and QgsProject.instance().absolutePath() != " ":
            self.fileGpkg.path = os.path.join(
                QgsProject.instance().absolutePath(), re.sub(r"[^\w]+", "_", self.inpPlanName.text()) + ".gpkg"
            )

    def numDistrictsChanged(self, value: int):
        self.sbxNumSeats.setMinimum(value)
        if self.linkSeats or self.field("numSeats") < value:
            self.sbxNumSeats.setValue(value)
            self.linkSeats = True
        self.completeChanged.emit()

    def numSeatsChanged(self, value: int):
        if value < self.field("numDistricts"):
            self.sbxNumSeats.setValue(self.field("numDistricts"))
        else:
            self.linkSeats = value == self.field("numDistricts")

    def isComplete(self) -> bool:
        complete = super().isComplete()
        return complete and self.field("numDistricts") > 1
