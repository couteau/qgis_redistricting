# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - table model wrapping plan manager list

        begin                : 2024-03-20
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
from qgis.PyQt.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSize,
    Qt
)
from qgis.PyQt.QtGui import (
    QColor,
    QFont
)

from ..models import RdsPlan
from ..utils import tr
from .planmgr import PlanManager


class PlanListModel(QAbstractTableModel):
    def __init__(self, planList: PlanManager, parent=None):
        super().__init__(parent)
        self.planList = planList
        self.planList.aboutToChangeActivePlan.connect(self.activePlanAboutToChange)
        self.planList.activePlanChanged.connect(self.activePlanChanged)
        self.planList.planAdded.connect(self.planAdded)
        self.planList.planRemoved.connect(self.planRemoved)
        self.planList.cleared.connect(self.planListUpdated)

        self.header = [
            tr('Plan'),
            tr('Districts'),
            tr('Description')
        ]

    def rowCount(self, parent: QModelIndex = ...) -> int:  # pylint: disable=unused-argument
        return len(self.planList)

    def columnCount(self, parent: QModelIndex = ...) -> int:  # pylint: disable=unused-argument
        return 3

    def headerData(self, section, orientation: Qt.Orientation, role):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self.header[section]
            if role == Qt.SizeHintRole:
                if section in (0, 2):
                    return QSize(150, 30)

        return None

    def data(self, index, role):
        if role == Qt.DisplayRole:
            plan = self.planList[index.row()]
            if index.column() == 0:
                v = plan.name
            elif index.column() == 1:
                v = f"{plan.numDistricts:,}"
            elif index.column() == 2:
                v = plan.description
            else:
                v = None
            return v
        elif role == Qt.TextAlignmentRole and index.column() == 1:
            return int(Qt.AlignRight | Qt.AlignCenter)
        elif role == Qt.FontRole:
            if index.row() == self.activePlanIndex().row():
                f = QFont()
                f.setBold(True)
                return f
        elif role == Qt.TextColorRole:
            if index.row() == self.activePlanIndex().row():
                return QColor(Qt.blue)

        return None

    @property
    def activePlan(self) -> RdsPlan:
        return self.planList.activePlan

    def indexFromPlan(self, plan: RdsPlan):
        try:
            row = self.planList.index(plan)
            return self.createIndex(row, 0)
        except:  # pylint: disable=bare-except
            pass

        return QModelIndex()

    def activePlanIndex(self) -> QModelIndex:
        if self.activePlan is None:
            return QModelIndex()

        return self.indexFromPlan(self.activePlan)

    def planFromIndex(self, index: QModelIndex) -> RdsPlan:
        if 0 <= index.row() < len(self.planList):
            return self.planList[index.row()]

        return None

    def planAdded(self, plan: RdsPlan):
        plan.nameChanged.connect(self.updatePlan)
        plan.numDistrictsChanged.connect(self.updatePlan)
        plan.descriptionChanged.connect(self.updatePlan)
        self.planListUpdated()

    def planRemoved(self, plan: RdsPlan):
        plan.nameChanged.disconnect(self.updatePlan)
        plan.numDistrictsChanged.disconnect(self.updatePlan)
        plan.descriptionChanged.disconnect(self.updatePlan)
        self.planListUpdated()

    def planListUpdated(self):
        self.beginResetModel()
        self.endResetModel()

    def updatePlan(self, plan):
        idx1 = self.indexFromPlan(plan)
        idx2 = self.createIndex(idx1.row(), self.columnCount() - 1)
        self.dataChanged.emit(idx1, idx2)

    def activePlanAboutToChange(self, oldPlan, newPlan):  # pylint: disable=unused-argument
        idx1 = self.indexFromPlan(oldPlan)
        idx2 = self.createIndex(idx1.row(), self.columnCount() - 1)
        self.dataChanged.emit(idx1, idx2, [Qt.FontRole, Qt.TextColorRole])

    def activePlanChanged(self, plan):
        idx1 = self.indexFromPlan(plan)
        idx2 = self.createIndex(idx1.row(), self.columnCount() - 1)
        self.dataChanged.emit(idx1, idx2, [Qt.FontRole, Qt.TextColorRole])
