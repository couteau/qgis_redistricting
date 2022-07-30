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
from qgis.PyQt.QtCore import Qt, QObject, QVariant, QAbstractTableModel, QModelIndex

from .Plan import RedistrictingPlan
from .DeltaList import DeltaList
from .Field import DataField
from .utils import tr, makeFieldName


class DeltaListModel(QAbstractTableModel):
    def __init__(self, plan: RedistrictingPlan, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plan = None
        self._fields = []
        self._delta = None
        self.setPlan(plan)

    def setPlan(self, plan: RedistrictingPlan):
        if plan != self._plan:
            if self._plan:
                self._plan.planChanged.disconnect(self.planChanged)
            self._plan = plan
            if self._plan:
                self._plan.planChanged.connect(self.planChanged)
                self.beginResetModel()
                self._delta = DeltaList(self._plan, self)
                self.updateFields()
                self._delta.updating.connect(self.startUpdate)
                self._delta.updateComplete.connect(self.endUpdate)
                self._delta.updateTerminated.connect(self.cancelUpdate)
                self.endResetModel()
            else:
                self._delta = None
                self._fields = []

    def updateFields(self):
        self._fields = [
            {
                'name': f'new_{self._plan.popField}',
                'caption': tr('Population'),
                'format': '{:,}'
            },
            {
                'name': self._plan.popField,
                'caption': tr('Population') + ' - ' + tr('Change'),
                'format': '{:+,}'
            },
            {
                'name': 'deviation',
                'caption': tr('Deviation'),
                'format': '{:,}'
            },
            {
                'name': 'pct_deviation',
                'caption': tr('%Deviation'),
                'format': '{:+.2%}'
            }
        ]

        if self._plan.vapField:
            self._fields.extend([
                {
                    'name': f'new_{self._plan.vapField}',
                    'caption': tr('VAP'),
                    'format': '{:,}'
                },
                {
                    'name': self._plan.vapField,
                    'caption': tr('VAP') + ' - ' + tr('Change'),
                    'format': '{:+,}'
                }
            ])

        if self._plan.cvapField:
            self._fields.extend([
                {
                    'name': f'new_{self._plan.cvapField}',
                    'caption': tr('CVAP'),
                    'format': '{:,}'
                },
                {
                    'name': self._plan.cvapField,
                    'caption': tr('CVAP') + ' - ' + tr('Change'),
                    'format': '{:+,}'
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
                        'format': '{:,}'
                    },
                    {
                        'name': fn,
                        'caption': field.caption + ' - ' + tr('Change'),
                        'format': '{:+,}'
                    }
                ])

            if field.pctbase:
                self._fields.append({
                    'name': f'pct_{fn}',
                    'caption': f'%{field.caption}',
                    'format': '{:.2%}'
                })

    def planChanged(self, plan, field, new, old):  # pylint: disable=unused-argument
        if field in {'pop-field', 'vap-field', 'cvap-field', 'data-fields'}:
            self.beginResetModel()
            self.updateFields()
            self.endResetModel()

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._delta) if self._delta and not parent.isValid() else 0

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._fields) if not parent.isValid() else 0

    def data(self, index: QModelIndex, role: int = ...):
        if self._delta:
            row = index.row()
            col = index.column()

            if role in {Qt.DisplayRole, Qt.EditRole}:
                dist = self._delta[col]
                if dist is not None:
                    value = dist[self._fields[row]['name']]
                    return self._fields[row]['format'].format(value) if value is not None else None

        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...):
        if self._delta:
            if role == Qt.DisplayRole:
                if orientation == Qt.Horizontal:
                    if self._delta[section] is not None:
                        return self._delta[section].name
                else:
                    return self._fields[section]['caption']
            if role == Qt.TextAlignmentRole:
                return int(Qt.AlignVCenter | Qt.AlignRight) if orientation == Qt.Vertical else int(Qt.AlignCenter)

        return QVariant()

    def startUpdate(self):
        self.beginResetModel()

    def endUpdate(self):
        self.endResetModel()

    def cancelUpdate(self):
        self.endResetModel()
