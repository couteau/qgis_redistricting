"""QGIS Redistricting Plugin - New District Dialog

        begin                : 2022-04-05
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

from typing import Optional, Union

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QWidget

from ..models import RdsPlan
from .ui.DlgNewDistrict import Ui_dlgNewDistrict


class DlgNewDistrict(Ui_dlgNewDistrict, QDialog):
    def __init__(
        self,
        plan: RdsPlan,
        parent: Optional[QWidget] = None,
        flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.WindowType.Dialog,
    ):
        super().__init__(parent, flags)
        self.setupUi(self)
        self.sbxDistrictNo.setValue(0)
        self.sbxDistrictNo.setPlan(plan)
        self.sbxDistrictNo.setMaximum(plan.numDistricts)

        seatsLeft = plan.numSeats - plan.allocatedSeats
        distsLeft = plan.numDistricts - plan.allocatedDistricts
        self.sbxMembers.setMaximum(seatsLeft - distsLeft + 1)
        self.sbxDistrictNo.valueChanged.connect(self.updateButton)

        i = 1
        for dist in plan.districts[1:]:
            if dist.district > i:
                break
            i = dist.district + 1

        if i > plan.numDistricts:
            # No more districts in the plan
            self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        else:
            self.sbxDistrictNo.setValue(i)

    def updateButton(self):
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(self.districtNumber))

    @property
    def districtNumber(self):
        return self.sbxDistrictNo.value()

    @property
    def districtName(self):
        return self.inpName.text()

    @property
    def members(self):
        return self.sbxMembers.value()

    @property
    def description(self):
        return self.txtDescription.toPlainText()
