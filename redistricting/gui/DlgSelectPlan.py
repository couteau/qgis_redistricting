# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QGIS Redistricting Plugin - Select Plan Dialog
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
 ***************************************************************************/

/***************************************************************************
 * *
 *   This program is free software; you can redistribute it and / or modify *
 *   it under the terms of the GNU General Public License as published by *
 *   the Free Software Foundation; either version 2 of the License, or *
 *   (at your option) any later version. *
 * *
 ***************************************************************************/
"""
from typing import Optional, Union
from qgis.PyQt.QtCore import Qt, pyqtSignal, QAbstractTableModel, QModelIndex
from qgis.PyQt.QtGui import QFont, QColor
from qgis.PyQt.QtWidgets import QWidget, QDialog, QHeaderView
from .ui.DlgSelectPlan import Ui_dlgSelectPlan
from ..core import RedistrictingPlan, tr


class PlanListModel(QAbstractTableModel):
    def __init__(self, planList, activePlan, parent=None):
        super().__init__(parent)
        self.planList = planList
        self.activePlan = activePlan

        self.header = [
            tr('Plan'),
            tr('Districts'),
            tr('Description')
        ]

    def rowCount(self, parent: QModelIndex = ...) -> int:  # pylint: disable=unused-argument
        return len(self.planList)

    def columnCount(self, parent: QModelIndex = ...) -> int:  # pylint: disable=unused-argument,no-self-use
        return 3

    def headerData(self, section, orientation: Qt.Orientation, role):
        if (role == Qt.DisplayRole and orientation == Qt.Horizontal):
            return self.header[section]
        return None

    def data(self, index, role):
        if role == Qt.DisplayRole:
            plan = self.planList[index.row()]
            if index.column() == 0:
                return plan.name
            elif index.column() == 1:
                return str(plan.numDistricts)
            elif index.column() == 2:
                return plan.description
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

    def activePlanIndex(self):
        if self.activePlan is not None:
            try:
                row = self.planList.index(self.activePlan)
                return self.createIndex(row, 0)
            except:  # pylint: disable=bare-except
                pass

        return QModelIndex()

    def plan(self, index):
        if 0 <= index.row() < len(self.planList):
            return self.planList[index.row()]
        return None

    def planListUpdate(self):
        self.beginResetModel()
        self.endResetModel()


class DlgSelectPlan(Ui_dlgSelectPlan, QDialog):
    planSelected = pyqtSignal(RedistrictingPlan)
    planEdited = pyqtSignal(RedistrictingPlan)
    planDeleted = pyqtSignal(RedistrictingPlan)

    def __init__(self, planList, activePlan, parent: Optional[QWidget] = None,
                 flags: Union[Qt.WindowFlags, Qt.WindowType] = Qt.Dialog):
        super().__init__(parent, flags)
        self.setupUi(self)
        self.model = PlanListModel(
            planList,
            activePlan,
            self
        )
        self.lvwPlans.setModel(self.model)
        self.lvwPlans.resizeColumnsToContents()
        self.lvwPlans.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.lvwPlans.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.lvwPlans.clicked.connect(self.updateButtons)
        self.lvwPlans.doubleClicked.connect(self.selectPlan)
        self.btnEdit.clicked.connect(self.editPlan)
        self.btnOpen.clicked.connect(self.selectPlan)
        self.btnDelete.clicked.connect(self.deletePlan)
        self.btnCancel.clicked.connect(self.reject)

        self.lvwPlans.setCurrentIndex(self.model.activePlanIndex())
        self.updateButtons(self.lvwPlans.currentIndex())

    def updateButtons(self, current: QModelIndex):
        self.btnOpen.setEnabled(
            self.plan(current) is not None and self.plan(current).isValid())
        self.btnEdit.setEnabled(self.plan(current) is not None)

    def plan(self, index) -> RedistrictingPlan:
        return self.model.plan(index)

    @property
    def currentPlan(self) -> RedistrictingPlan:
        index = self.lvwPlans.currentIndex()
        return self.model.plan(index)

    def editPlan(self):
        plan = self.currentPlan
        if plan:
            self.planEdited.emit(plan)
            self.accept()

    def selectPlan(self):
        plan = self.currentPlan
        if plan and plan.isValid():
            self.planSelected.emit(plan)
            self.accept()

    def deletePlan(self):
        plan = self.currentPlan
        if plan:
            self.planDeleted.emit(plan)
            self.model.planListUpdate()
