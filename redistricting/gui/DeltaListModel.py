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
    Qt,
    QVariant
)

from ..models import (
    DataField,
    Field,
    RedistrictingPlan,
    makeFieldName
)
from ..utils import tr


class DeltaListModel(QAbstractTableModel):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plan = None
        self._fields = []
        self._delta = None

    def setPlan(self, plan: RedistrictingPlan):
        if plan != self._plan:
            self.beginResetModel()
            if self._plan:
                self._plan.popFieldChanged.disconnect(self.updateFields)
                self._plan.popFieldsChanged.disconnect(self.updateFields)
                self._plan.dataFieldsChanged.disconnect(self.updateFields)
                self._delta.updateStarted.disconnect(self.startUpdate)
                self._delta.updateComplete.disconnect(self.endUpdate)
            self._plan = plan
            if self._plan:
                self._plan.popFieldChanged.connect(self.updateFields)
                self._plan.popFieldsChanged.connect(self.updateFields)
                self._plan.dataFieldsChanged.connect(self.updateFields)
                self._delta = self._plan.delta
                self.updateFields()
                self._delta.updateStarted.connect(self.startUpdate)
                self._delta.updateComplete.connect(self.endUpdate)
            else:
                self._delta = None
                self._fields = []

            self.endResetModel()

    def updateFields(self):
        self._fields = [
            {
                'name': f'new_{self._plan.popField}',
                'caption': tr('Population'),
                'format': '{:,.0f}'
            },
            {
                'name': self._plan.popField,
                'caption': tr('Population') + ' - ' + tr('Change'),
                'format': '{:+,.0f}'
            },
            {
                'name': 'deviation',
                'caption': tr('Deviation'),
                'format': '{:,.0f}'
            },
            {
                'name': 'pct_deviation',
                'caption': tr('%Deviation'),
                'format': '{:+.2%}'
            }
        ]

        field: Field
        for field in self._plan.popFields:
            fn = makeFieldName(field)
            self._fields.extend([
                {
                    'name': f'new_{fn}',
                    'caption': field.caption,
                    'format': '{:,.0f}'
                },
                {
                    'name': fn,
                    'caption': field.caption + ' - ' + tr('Change'),
                    'format': '{:+,.0f}'
                }
            ])

        field: DataField
        for field in self._plan.dataFields:
            fn = makeFieldName(field)
            if field.sum:
                self._fields.extend([
                    {
                        'name': f'new_{fn}',
                        'caption': field.caption,
                        'format': '{:,.0f}'
                    },
                    {
                        'name': fn,
                        'caption': field.caption + ' - ' + tr('Change'),
                        'format': '{:+,.0f}'
                    }
                ])

            if field.pctbase:
                self._fields.append({
                    'name': f'pct_{fn}',
                    'caption': f'%{field.caption}',
                    'format': '{:.2%}'
                })

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._delta) if self._delta and not parent.isValid() else 0

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._fields) if not parent.isValid() else 0

    def data(self, index: QModelIndex, role: int = ...):
        if self._delta:
            row = index.row()
            col = index.column()

            if role in {Qt.DisplayRole, Qt.EditRole}:
                value = self._delta[col, row]
                return self._fields[row]['format'].format(value) if value is not None else None

        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...):
        if self._delta:
            if role == Qt.DisplayRole:
                if orientation == Qt.Horizontal:
                    return self._delta[section].name
                else:
                    return self._fields[section]['caption']
            if role == Qt.TextAlignmentRole:
                return int(Qt.AlignVCenter | Qt.AlignRight) if orientation == Qt.Vertical else int(Qt.AlignCenter)

        return QVariant()

    def startUpdate(self, plan):
        if plan == self._plan:
            self.beginResetModel()

    def endUpdate(self, plan):
        if plan == self._plan:
            self.endResetModel()