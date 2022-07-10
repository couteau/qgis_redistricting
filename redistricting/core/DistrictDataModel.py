# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RedistrictingPlan
        QGIS Redistricting plugin model for display of plan data
                              -------------------
        begin                : 2022-03-21
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from numbers import Number
from typing import Any
from qgis.PyQt.QtCore import Qt, QVariant, QObject, QAbstractTableModel, QModelIndex
from qgis.PyQt.QtGui import QBrush, QColor
from .DistrictList import DistrictList
from .Plan import RedistrictingPlan
from .Utils import tr, makeFieldName


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
            self._districts.districtAdded.disconnect(self.districtAdded)
            self._districts.districtRemoved.disconnect(self.districtRemoved)
            self._districts.updating.disconnect(self.beginResetModel)
            self._districts.updateComplete.disconnect(self.endResetModel)
            self._districts.updateTerminated.disconnect(self.endResetModel)
            self._plan.planChanged.disconnect(self.planChanged)

        self._plan = value
        self._districts = self._plan.districts if self._plan else None

        if self._districts is not None:
            self.updateColumnKeys()
            self._districts.districtAdded.connect(self.districtAdded)
            self._districts.districtRemoved.connect(self.districtRemoved)
            self._districts.updating.connect(self.beginResetModel)
            self._districts.updateComplete.connect(self.endResetModel)
            self._districts.updateTerminated.connect(self.endResetModel)
            self._plan.planChanged.connect(self.planChanged)
        else:
            self._headings = []
            self._keys = []

        self.endResetModel()

    def updateColumnKeys(self):
        self._keys = ['district', 'name',
                      self._plan.popField, 'deviation', 'pct_deviation']

        self._headings = [
            tr('District'),
            tr('Name'),
            tr('Population'),
            tr('Deviation'),
            tr('%Deviation')
        ]

        if self._plan.vapField:
            self._keys.append(self._plan.vapField)
            self._headings.append(tr('VAP'))

        if self._plan.cvapField:
            self._keys.append(self._plan.cvapField)
            self._headings.append(tr('CVAP'))
        for field in self._plan.dataFields:
            fn = makeFieldName(field)
            if field.sum:
                self._keys.append(fn)
                self._headings.append(field.caption)
            if field.pctbase:
                self._keys.append(f'pct_{fn}')
                self._headings.append(f'%{field.caption}')
        self._keys += ['polsbyPopper', 'reock', 'convexHull']
        self._headings += [
            tr('Polsby-Popper'),
            tr('Reock'),
            tr('Convex Hull'),
        ]

    def districtAdded(self, plan, dist, index):  # pylint: disable=unused-argument
        # if plan != self._plan:
        #    return

        self.beginInsertRows(QModelIndex(), index, index)
        self.endInsertRows()

    def districtRemoved(self, plan, dist, index):  # pylint: disable=unused-argument
        # if plan != self._plan:
        #    return

        self.beginRemoveRows(QModelIndex(), index, index)
        self.endRemoveRows()

    def planChanged(self, plan, prop, value, oldValue):  # pylint: disable=unused-argument
        if prop in ('data-fields', 'pop-field', 'vap-field', 'cvap-field'):
            self.beginResetModel()
            self.updateColumnKeys()
            self.endResetModel()
        elif prop == 'deviation':
            self.dataChanged.emit(self.createIndex(1, 1), self.createIndex(self.rowCount() - 1, 4), [Qt.BackgroundRole])

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._districts) if self._districts and not parent.isValid() else 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headings) if not parent.isValid() else 0

    def data(self, index, role=Qt.DisplayRole):
        if role in (Qt.DisplayRole, Qt.EditRole):
            self._districts.updateDistricts()

            row = index.row()
            column = index.column()

            key = self._keys[column]
            value = getattr(self._districts[row], key)

            if value is None:
                return QVariant()

            if key == 'deviation':
                value = f'{value:+,}'
            elif key == 'pct_deviation':
                value = f'{value:+.2%}'
            elif key in {'polsbyPopper', 'reock', 'convexHull'}:
                value = f'{value:.3}'
            elif key[:3] == 'pct':
                value = f'{value:.2%}'
            elif isinstance(value, Number):
                value = f'{value:,}'
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
                elif self._districts[row].valid:
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
            return self._headings[section]

        return None

    def flags(self, index):
        f = super().flags(index)
        if index.column() == 1 and index.row() != 0:
            f |= Qt.ItemIsEditable

        return f
