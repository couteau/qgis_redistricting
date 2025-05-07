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

from qgis.PyQt.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt
from qgis.PyQt.QtWidgets import QDialog, QStyledItemDelegate, QStyleOptionViewItem, QTreeView, QWidget

from ..models import RdsPlan, RdsSplits, RdsSplitsModel
from ..models.base.lists import KeyedList
from ..utils import tr
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
    def __init__(self, plan: RdsPlan, parent: Optional[QWidget] = None, flags: Qt.WindowType = Qt.WindowType.Dialog):
        super().__init__(parent, flags)
        self.setupUi(self)

        self._plan = plan
        self._splits: KeyedList[RdsSplits] = plan.metrics.splits
        self._field: str = None
        self._plan.nameChanged.connect(self.planNameChanged)
        self._plan.geoFieldsChanged.connect(self.updateGeography)
        self.updateGeography()

        self.lblPlan.setText(self._plan.name)
        self.cmbGeography.currentIndexChanged.connect(self.changeGeography)
        self.tvSplits.setItemDelegateForColumn(1, RdsSplitDistrictsDelegate(self.tvSplits))

    @property
    def plan(self):
        return self._plan

    @property
    def field(self) -> str:
        return self._field

    @field.setter
    def field(self, value: str):
        if value not in self._splits.keys():
            raise ValueError("No splits data for field")

        if self._field == value:
            return

        self._field = value
        geoField = self._plan.geoFields[value]
        self.setWindowTitle(f"{geoField.caption} {tr('Splits')}")
        self.cmbGeography.setCurrentText(geoField.caption)

        model = RdsSplitsModel(self._splits[self._field], (*self._plan.popFields, *self._plan.dataFields))
        self.setModel(model)

    def model(self):
        return self.tvSplits.model()

    def setModel(self, value: QAbstractItemModel):
        self.tvSplits.setModel(value)

    def planNameChanged(self):
        self.lblPlan.setText(self._plan.name)

    def updateGeography(self):
        self.cmbGeography.clear()
        self.cmbGeography.addItems([f.caption for f in self._plan.geoFields])

    def changeGeography(self, idx: int):
        self.field = self._splits.get_key(idx)
