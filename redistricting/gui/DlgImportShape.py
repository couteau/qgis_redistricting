# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DlgEditPlan
        QGIS Redistricting Plugin - Export Plan Dialog
                              -------------------
        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
 ***************************************************************************/

/***************************************************************************
 * *
 *   This program is free software; you can redistribute it and / or modify *
 *   it under the terms of the GNU General Public License as published by *
 *   the Free Software Foundation; either version 2 of the License, or *
 *   (at your option) any later version. *
 * *
 ***************************************************************************/
"""
from typing import Optional, Union

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QWidget, QDialogButtonBox
from qgis.core import QgsVectorLayer
from .ui.DlgImportShapefile import Ui_dlgImportShapefile
from ..core import RedistrictingPlan


class DlgImportShape(Ui_dlgImportShapefile, QDialog):
    def __init__(self, plan: RedistrictingPlan, parent: Optional[QWidget] = None, flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.Dialog):
        super().__init__(parent, flags)
        self.setupUi(self)

        self.layer = None
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        self.fwShapefile.fileChanged.connect(self.fileChanged)
        self.cmbDistField.fieldChanged.connect(self.updateButton)

    def fileChanged(self):
        self.layer = QgsVectorLayer(self.fwShapefile.filePath())
        self.cmbDistField.setLayer(self.layer)
        self.cmbNameField.setLayer(self.layer)
        self.cmbMembersField.setLayer(self.layer)
        self.updateButton()

    def updateButton(self):
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(
            bool(self.shapefileFileName) and bool(self.distField)
        )

    @property
    def shapefileFileName(self):
        return self.fwShapefile.filePath()

    @property
    def distField(self):
        return self.cmbDistField.currentField()

    @property
    def nameField(self):
        return self.cmbNameField.currentField()

    @property
    def membersField(self):
        return self.cmbMembersField.currentField()