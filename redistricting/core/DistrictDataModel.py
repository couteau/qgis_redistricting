# -*- coding: utf-8 -*-
"""Qt Model/View model for display of plan data
                              -------------------
        begin                : 2022-03-21
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
from typing import Any

import pandas as pd
from qgis.PyQt.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    QVariant
)
from qgis.PyQt.QtGui import (
    QBrush,
    QColor
)

from .DistrictList import DistrictList
from .Plan import RedistrictingPlan


class DistrictDataModel(QAbstractTableModel):
    _plan: RedistrictingPlan = None

    def __init__(self, plan: RedistrictingPlan = None, parent: QObject = None):
        super().__init__(parent)
        self._keys = []
        self._headings = []
        self._districts: DistrictList = None
        self.plan = plan

    @ property
    def plan(self) -> RedistrictingPlan:
        return self._plan

    @ plan.setter
    def plan(self, value: RedistrictingPlan):
        self.beginResetModel()

        if self._districts is not None:
            self._districts.updating.disconnect(self.beginResetModel)
            self._districts.updateComplete.disconnect(self.endResetModel)
            self._districts.updateTerminated.disconnect(self.endResetModel)
            self._plan.planChanged.disconnect(self.planChanged)

        self._plan = value
        self._districts = self._plan.districts if self._plan else None

        if self._districts is not None:
            self._districts.updating.connect(self.beginResetModel)
            self._districts.updateComplete.connect(self.endResetModel)
            self._districts.updateTerminated.connect(self.endResetModel)
            self._plan.planChanged.connect(self.planChanged)

        self.endResetModel()

    def planChanged(self, plan, prop, value, oldValue):  # pylint: disable=unused-argument
        if prop in ('districts', 'data-fields', 'pop-field', 'pop-fields'):
            self.beginResetModel()
            self.endResetModel()
        elif prop == 'deviation':
            self.dataChanged.emit(self.createIndex(1, 1), self.createIndex(self.rowCount() - 1, 4), [Qt.BackgroundRole])

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._districts) if self._districts and not parent.isValid() else 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() or self._districts is None:
            return 0

        return len(self._districts.data.columns)

    def data(self, index, role=Qt.DisplayRole):
        if role in (Qt.DisplayRole, Qt.EditRole):
            self._districts.updateDistricts()

            row = index.row()
            column = index.column()

            key = self._districts.data.columns[column]
            value = self._districts.data.iat[row, column]

            if pd.isna(value):
                return QVariant()

            if key == 'deviation':
                value = f'{value:+,}'
            elif key == 'pct_deviation':
                value = f'{value:+.2%}'
            elif key in {'polsbypopper', 'reock', 'convexhull'}:
                value = f'{value:.3}'
            elif key[:3] == 'pct':
                value = f'{value:.2%}'
            elif isinstance(value, int):
                value = f'{value:,}'
            elif isinstance(value, float):
                value = f'{value:,.2f}'
            return value

        if role == Qt.BackgroundRole:
            self._districts.updateDistricts()

            brush = QVariant()
            row = index.row()
            col = index.column()
            if col == 0:
                brush = QBrush(self._districts[row].color) if row != 0 else QBrush(QColor(160, 160, 160))
            elif 1 <= col <= 4:
                if row == 0:
                    brush = QBrush(QColor(160, 160, 160))
                elif self._districts[row].isValid():
                    brush = QBrush(QColor(178, 223, 138))
            return brush

        return QVariant()

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        if role == Qt.EditRole and index.column() == 1 and index.row() != 0:
            dist = self._districts[index.row()]
            dist.name = value
            self.dataChanged.emit(index, index, {Qt.DisplayRole})
            return True

        return False

    def headerData(self, section, orientation: Qt.Orientation, role):
        if (role == Qt.DisplayRole and orientation == Qt.Horizontal):
            return self._districts.heading[section]

        return None

    def flags(self, index):
        f = super().flags(index)
        if index.column() == 1 and index.row() != 0:
            f |= Qt.ItemIsEditable

        return f
