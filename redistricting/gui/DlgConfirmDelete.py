# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DlgConfirmDelete
        QGIS Redistricting Plugin - Confirm Delete Plan Dialog
                              -------------------
        begin                : 2022-04-21
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
from qgis.PyQt.QtWidgets import QDialog, QWidget
from .ui.DlgConfirmDelete import Ui_dlgConfirmDelete
from ..core import RedistrictingPlan, tr


class DlgConfirmDelete(Ui_dlgConfirmDelete, QDialog):
    def __init__(self, plan: RedistrictingPlan, parent: Optional[QWidget] = None, flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.Dialog):
        super().__init__(parent, flags)
        self.setupUi(self)
        self.setWindowTitle(tr('Confirm Delete {name}').format(name=plan.name))

    def removeLayers(self):
        return self.cbxRemoveLayers.isChecked()

    def deleteGeoPackage(self):
        return self.cbxDeleteLayers.isChecked()
