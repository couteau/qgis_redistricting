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
from typing import (
    Any,
    Union
)

import numpy as np
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
    QColor,
    QFont
)

from .District import District
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
            self._districts.districtChanged.disconnect(self.districtChanged)
            self._plan.districtsUpdated.disconnect(self.districtsUpdated)
            self._plan.planChanged.disconnect(self.planChanged)

        self._plan = value
        self._districts = self._plan.districts if self._plan else None

        if self._districts is not None:
            self._districts.districtChanged.connect(self.districtChanged)
            self._plan.districtsUpdated.connect(self.districtsUpdated)
            self._plan.planChanged.connect(self.planChanged)

        self.endResetModel()

    def planChanged(self, plan, props):
        assert plan == self.plan

        if props & {'districts', 'data-fields', 'pop-field', 'pop-fields'}:
            self.beginResetModel()
            self.endResetModel()
        elif 'deviation' in props:
            self.dataChanged.emit(self.createIndex(1, 1), self.createIndex(self.rowCount() - 1, 4), [Qt.BackgroundRole])

    def districtChanged(self, district: District):
        row = self._districts.index(district)
        start = self.createIndex(row, 1)
        end = self.createIndex(row, self.columnCount())
        self.dataChanged.emit(start, end, {Qt.DisplayRole, Qt.EditRole, Qt.BackgroundRole})

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._districts) if self._districts and not parent.isValid() else 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() or self._districts is None:
            return 0

        return len(self._districts.columns)

    def data(self, index, role=Qt.DisplayRole):
        value = QVariant()
        if role in (Qt.DisplayRole, Qt.EditRole):
            row = index.row()
            col = index.column()

            if row == 0:
                if col == 0:
                    return self._districts[0, "name"]
                if col == 1:
                    return QVariant()

            value = self._districts[row, col]
            if pd.isna(value):
                return QVariant()

            key = self._districts.columns[col]
            if key == 'deviation':
                value = f'{value:+,}'
            elif key == 'pct_deviation':
                value = f'{value:+.2%}'
            elif key in {'polsbypopper', 'reock', 'convexhull'}:
                value = f'{value:.3}'
            elif key[:3] == 'pct':
                value = f'{value:.2%}'
            elif isinstance(value, (int, np.integer)):
                value = f'{value:,}'
            elif isinstance(value, (float, np.floating)):
                value = f'{value:,.2f}'

        elif role == Qt.BackgroundRole:
            row = index.row()
            col = index.column()
            if col == 0:
                value = QBrush(self._districts[row].color) if row != 0 else QBrush(QColor(160, 160, 160))

        elif role == Qt.FontRole:
            row = index.row()
            col = index.column()
            if row > 0 and col in {0, 4, 5}:
                value = QFont()
                value.setBold(True)

        elif role == Qt.TextAlignmentRole:
            if index.column() == 0:
                value = Qt.AlignCenter

        elif role == Qt.TextColorRole:
            row = index.row()
            col = index.column()
            if col == 0:
                value = QColor(55, 55, 55)
            elif 4 <= col <= 5:
                if self._districts[row].isValid():
                    value = QColor(99, 196, 101)
                else:
                    value = QColor(207, 99, 92)

        return value

    def setData(self, index: QModelIndex, value: Any, role: int) -> bool:
        if role == Qt.EditRole and index.column() == 1 and index.row() != 0:
            dist = self._districts[index.row()]
            dist.name = value
            self.dataChanged.emit(index, index, {Qt.DisplayRole})
            return True

        return False

    def headerData(self, section, orientation: Qt.Orientation, role):
        if (role == Qt.DisplayRole and orientation == Qt.Horizontal):
            return self._districts.headings[section]

        return None

    def flags(self, index):
        f = super().flags(index)
        if index.column() == 1 and index.row() != 0:
            f |= Qt.ItemIsEditable

        return f

    def districtsUpdated(self, districts: Union[list[int], None]):
        if districts:
            for d in districts:
                self.dataChanged.emit(
                    self.createIndex(d, 3),
                    self.createIndex(d, self.columnCount()),
                    [Qt.DisplayRole, Qt.EditRole]
                )
                self.dataChanged.emit(self.createIndex(d, 4), self.createIndex(d, 5), [Qt.FontRole])
        else:
            self.beginResetModel()
            self.endResetModel()
