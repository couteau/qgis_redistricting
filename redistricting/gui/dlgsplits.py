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
from typing import Optional

from qgis.PyQt.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QObject,
    Qt,
    pyqtSignal
)
from qgis.PyQt.QtWidgets import (
    QDialog,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeView,
    QWidget
)

from ..models import RdsPlan
from .ui.DlgSplits import Ui_dlgSplits


class RdsSplitDistrictsDelegate(QStyledItemDelegate):
    """Hide display of comma-delimited list of districts for expanded geographies"""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        if isinstance(parent, QTreeView):
            self._view = parent
        else:
            self._view = None

    def setParent(self, parent: QObject) -> None:
        super().setParent(parent)
        if isinstance(parent, QTreeView):
            self._view = parent

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex):
        super().initStyleOption(option, index)
        if self._view is not None and self._view.isExpanded(index.siblingAtColumn(0)):
            option.text = ""


class DlgSplitDetail(Ui_dlgSplits, QDialog):
    geographyChanged = pyqtSignal(int)

    def __init__(
            self,
            plan: RdsPlan,
            parent: Optional[QWidget] = None,
            flags: Qt.WindowType = Qt.WindowType.Dialog
    ):
        super().__init__(parent, flags)
        self.setupUi(self)

        self._plan: RdsPlan = plan
        self._plan.nameChanged.connect(self.planNameChanged)
        self._plan.geoFieldsChanged.connect(self.updateGeography)
        self.updateGeography()

        self.lblPlan.setText(self._plan.name)
        self.cmbGeography.currentIndexChanged.connect(self.geographyChanged)
        self.tvSplits.setItemDelegateForColumn(1, RdsSplitDistrictsDelegate(self.tvSplits))

    def model(self):
        return self.tvSplits.model()

    def setModel(self, value: QAbstractItemModel):
        self.tvSplits.setModel(value)

    def planNameChanged(self):
        self.lblPlan.setText(self._plan.name)

    def updateGeography(self):
        self.cmbGeography.clear()
        self.cmbGeography.addItems([f.caption for f in self._plan.geoFields])
