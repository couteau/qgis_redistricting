# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - Export Plan Dialog

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

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QWidget
)

from .ui.DlgExportPlan import Ui_dlgExportPlan


class DlgExportPlan(Ui_dlgExportPlan, QDialog):
    def __init__(self, parent: Optional[QWidget] = None, flags: Qt.WindowType = Qt.WindowType.Dialog):
        super().__init__(parent, flags)
        self.setupUi(self)

        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.fwEquivalency.lineEdit().setEnabled(False)
        self.fwShape.lineEdit().setEnabled(False)

        self.cbxExportEquivalency.toggled.connect(self.updateButton)
        self.fwEquivalency.fileChanged.connect(self.updateButton)
        self.cbxExportShape.toggled.connect(self.updateButton)
        self.fwShape.fileChanged.connect(self.updateButton)

    def updateButton(self):
        self.cbxExportEquivalency.setChecked(
            self.cbxExportEquivalency.isChecked() or bool(self.fwEquivalency.filePath())
        )
        self.cbxExportShape.setChecked(
            bool(self.cbxExportShape.isChecked() or self.fwShape.filePath()))
        self.fwEquivalency.lineEdit().setEnabled(self.cbxExportEquivalency.isChecked())
        self.fwShape.lineEdit().setEnabled(self.cbxExportShape.isChecked())
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            bool((self.exportEquivalency and self.equivalencyFileName) or
                 (self.exportShapefile and self.shapefileFileName))
        )

    @property
    def exportEquivalency(self):
        return self.cbxExportEquivalency.isChecked()

    @property
    def equivalencyFileName(self):
        return self.fwEquivalency.filePath()

    @property
    def equivalencyGeography(self):
        m = self.cmbGeography.model()
        return m.fields[self.cmbGeography.currentIndex()]

    @property
    def exportShapefile(self):
        return self.cbxExportShape.isChecked()

    @property
    def shapefileFileName(self):
        return self.fwShape.filePath()

    @property
    def includeUnassigned(self):
        return self.cbxIncludeUnassigned.isChecked()

    @property
    def includeDemographics(self):
        return self.cbxDemographics.isChecked()

    @property
    def includeMetrics(self):
        return self.cbxMetrics.isChecked()
