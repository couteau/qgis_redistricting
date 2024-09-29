# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - Qt Model/View model for pending changes

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
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    QVariant
)
from qgis.PyQt.QtGui import QBrush

from ..models import (
    DeltaList,
    DistrictColumns,
    FieldCategory,
    FieldColors,
    RdsDataField,
    RdsField,
    RdsPlan
)
from ..utils import tr


class DeltaListModel(QAbstractTableModel):
    FieldTypeRole = Qt.UserRole + 1

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plan = None
        self._fields = []
        self._delta: DeltaList = None

    @property
    def plan(self):
        return self._plan

    def setDelta(self, plan: RdsPlan, delta: DeltaList):
        if plan != self._plan or delta != self._delta:
            self.beginResetModel()
            if plan != self._plan:
                if self._plan is not None:
                    self._plan.popFieldChanged.disconnect(self.updateFields)
                    self._plan.popFieldsChanged.disconnect(self.updateFields)
                    self._plan.dataFieldsChanged.disconnect(self.updateFields)

                self._plan = plan

                if self._plan is not None:
                    self._plan.popFieldChanged.connect(self.updateFields)
                    self._plan.popFieldsChanged.connect(self.updateFields)
                    self._plan.dataFieldsChanged.connect(self.updateFields)
                    self.updateFields()
                else:
                    self._fields = []

            if delta != self._delta:
                if self._delta is not None:
                    self._delta.updateStarted.disconnect(self.startUpdate)
                    self._delta.updateComplete.disconnect(self.endUpdate)

                self._delta = delta

                if self._delta is not None:
                    self._delta.updateStarted.connect(self.startUpdate)
                    self._delta.updateComplete.connect(self.endUpdate)

            self.endResetModel()

    def updateFields(self):
        self._fields = [
            {
                'name': f'new_{DistrictColumns.POPULATION}',
                'caption': DistrictColumns.POPULATION.comment,  # pylint: disable=no-member
                'format': '{:,.0f}',
                'field-type': FieldCategory.Population
            },
            {
                'name': DistrictColumns.POPULATION,
                'caption': f'{DistrictColumns.POPULATION.comment} - {tr("Change")}',  # pylint: disable=no-member
                'format': '{:+,.0f}',
                'field-type': FieldCategory.Population
            },
            {
                'name': DistrictColumns.DEVIATION,
                'caption': DistrictColumns.DEVIATION.comment,  # pylint: disable=no-member
                'format': '{:,.0f}',
                'field-type': FieldCategory.Population
            },
            {
                'name': DistrictColumns.PCT_DEVIATION,
                'caption': DistrictColumns.PCT_DEVIATION.comment,  # pylint: disable=no-member
                'format': '{:+.2%}',
                'field-type': FieldCategory.Population
            }
        ]

        field: RdsField
        for field in self._plan.popFields:
            fn = field.fieldName
            self._fields.extend([
                {
                    'name': f'new_{fn}',
                    'caption': field.caption,
                    'format': '{:,.0f}',
                    'field-type': field.category
                },
                {
                    'name': fn,
                    'caption': f'{field.caption} - {tr("Change")}',
                    'format': '{:+,.0f}',
                    'field-type': field.category
                }
            ])

        field: RdsDataField
        for field in self._plan.dataFields:
            fn = field.fieldName
            if field.sumField:
                self._fields.extend([
                    {
                        'name': f'new_{fn}',
                        'caption': field.caption,
                        'format': '{:,.0f}',
                        'field-type': field.category
                    },
                    {
                        'name': fn,
                        'caption': field.caption + ' - ' + tr('Change'),
                        'format': '{:+,.0f}',
                        'field-type': field.category
                    }
                ])

            if field.pctBase:
                self._fields.append({
                    'name': f'pct_{fn}',
                    'caption': f'%{field.caption}',
                    'format': '{:.2%}',
                    'field-type': field.category
                })

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._delta) if self._delta is not None and not parent.isValid() else 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._fields) if not parent.isValid() else 0

    def data(self, index: QModelIndex, role: int = ...):
        if self._delta:
            row = index.row()
            col = index.column()

            if role in {Qt.DisplayRole, Qt.EditRole}:
                value = self._delta[row, col]
                return self._fields[col]['format'].format(value) if value is not None else None

            if role == DeltaListModel.FieldTypeRole:
                return self._fields[col]['field-type']

        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...):
        if self._delta:
            if role == Qt.DisplayRole:
                if orientation == Qt.Vertical:
                    return self._delta[section].name
                else:
                    return self._fields[section]['caption']
            if role == Qt.TextAlignmentRole:
                return int(Qt.AlignVCenter | Qt.AlignRight) if orientation == Qt.Horizontal else int(Qt.AlignCenter)

            if role == Qt.BackgroundRole and orientation == Qt.Horizontal:
                ft = self._fields[section]['field-type']
                if ft in FieldColors:
                    return QBrush(FieldColors[ft])

            if role == DeltaListModel.FieldTypeRole and orientation == Qt.Horizontal:
                return self._fields[section]['field-type']

        return None

    def startUpdate(self):
        self.beginResetModel()

    def endUpdate(self):
        self.endResetModel()


class DeltaFieldFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plan = None
        self._connection = None
        self._demographics: bool = True

    @property
    def deltaModel(self) -> DeltaListModel:
        return self.sourceModel()

    @property
    def plan(self):
        return self._plan

    def showDemographics(self, show: bool = True):
        if show != self._demographics:
            self._demographics = show
            self.invalidateFilter()

    def filterAcceptsColumn(self, source_column: int, source_parent: QModelIndex) -> bool:  # pylint: disable=unused-argument
        field_type = self.deltaModel._fields[source_column]['field-type']  # pylint: disable=protected-access
        return field_type == FieldCategory.Population or self._demographics
