# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - Confirm Delete Plan Dialog

        begin                : 2022-04-21
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
    QWidget
)

from ..models import RedistrictingPlan
from ..utils import tr
from .ui.DlgConfirmDelete import Ui_dlgConfirmDelete


class DlgConfirmDelete(Ui_dlgConfirmDelete, QDialog):
    def __init__(self, plan: RedistrictingPlan, parent: Optional[QWidget] = None, flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.Dialog):
        super().__init__(parent, flags)
        self.setupUi(self)
        self.setWindowTitle(tr('Confirm Delete {name}').format(name=plan.name))

    def removeLayers(self):
        return self.cbxRemoveLayers.isChecked()

    def deleteGeoPackage(self):
        return self.cbxDeleteLayers.isChecked()
