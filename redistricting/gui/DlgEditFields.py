# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DlgEditPlan
        QGIS Redistricting Plugin - Edit Data Fields dialog
                              -------------------
        begin                : 2022-06-07
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
from qgis.PyQt.QtWidgets import QDialog, QWidget, QDialogButtonBox, QVBoxLayout
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
        self.page.fexDataField.setLayer(plan.popLayer or plan.sourceLayer)
        self.page.fieldsModel.vapEnabled = bool(plan.vapField)
        self.page.fieldsModel.cvapEnabled = bool(plan.cvapField)

    def accept(self):
        self.plan.dataFields = self.page.field('dataFields')
        super().accept()
