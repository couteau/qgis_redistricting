# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - splits model

         begin                : 2024-02-18
         git sha              : $Format:%H$
         copyright            : (C) 2024 by Cryptodira
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
    Optional,
    Union
)

import numpy as np
import pandas as pd
from qgis.PyQt.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QObject,
    Qt,
    QVariant
)

from ..models import (
    RdsSplitDistrict,
    RdsSplitGeography,
    RdsSplits
)


class SplitsModel(QAbstractItemModel):
    def __init__(self, splits: RdsSplits, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._splits = splits
        self._splits.splitUpdating.connect(self.beginResetModel)
        self._splits.splitUpdated.connect(self.endResetModel)
        self._data: pd.DataFrame = splits.data

    def rowCount(self, parent: QModelIndex = ...) -> int:
        if not parent.isValid():  # it's the root node
            return len(self._splits)

        if parent.column() > 0:
            return 0

        split: Union[RdsSplitGeography, RdsSplitDistrict] = parent.internalPointer()
        if isinstance(split, RdsSplitGeography):
            return len(split)

        return 0

    def columnCount(self, parent: QModelIndex = ...) -> int:
        if not parent.isValid():
            return max(2, self._splits.attrCount)

        split: Union[RdsSplitGeography, RdsSplitDistrict] = parent.internalPointer()
        if isinstance(split, RdsSplitGeography):
            return self._splits.attrCount

        return 0

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags

        return super().flags(index)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if not index.isValid():
            return QVariant()

        item: Union[RdsSplitGeography, RdsSplits] = index.internalPointer()
        col = index.column()
        if isinstance(item, RdsSplitGeography):
            if col >= 2:
                return QVariant()
        else:
            if col == 0:
                return QVariant()
            col -= 1

        if role == Qt.DisplayRole:
            value = item.attributes[col]
            if isinstance(value, (int, np.integer)):
                value = f'{value:,}'
            elif isinstance(value, (float, np.floating)):
                value = f'{value:,.2f}'
            return value

        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...) -> Any:
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self._splits.header[section]

        return QVariant()

    def index(self, row: int, column: int, parent: QModelIndex = ...) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            return self.createIndex(row, column, self._splits[row])

        parentItem: Union[RdsSplitGeography, RdsSplitDistrict] = parent.internalPointer()
        if isinstance(parentItem, RdsSplitDistrict):  # shouldn't happen
            return QModelIndex()

        return self.createIndex(row, column, parentItem[row])

    def parent(self, index: QModelIndex = ...) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        split: Union[RdsSplitGeography, RdsSplitDistrict] = index.internalPointer()
        if isinstance(split, RdsSplitDistrict):
            return self.createIndex(split.parent.row, 0, split.parent)

        return QModelIndex()
