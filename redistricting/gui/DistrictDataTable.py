# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - A QDockWidget that shows selected demographic 
        data for the active Redistricting Plan

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
import os
import io
import csv
from typing import Any, Dict, Optional
from qgis.PyQt.QtCore import Qt, QObject, QCoreApplication, QEvent, QModelIndex, QAbstractTableModel
from qgis.PyQt.QtGui import QKeySequence, QFont
from qgis.PyQt.QtWidgets import QWidget, QDockWidget
from qgis.core import QgsApplication
from ..core import RedistrictingPlan, DistrictDataModel, Field, tr, showHelp
from .RdsOverlayWidget import OverlayWidget
from .ui.DistrictDataTable import Ui_qdwDistrictData
from .DlgEditFields import DlgEditFields


class StatsModel(QAbstractTableModel):
    StatLabels = [
        tr('Population'),
        tr('Avg. Polsby-Popper'),
        tr('Avg. Reock'),
        tr('Avg. Convex-Hull'),
        tr('Cut Edges'),
        tr('Splits')
    ]

    def __init__(self, plan: RedistrictingPlan, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plan = None
        self.plan = plan

    @property
    def plan(self) -> RedistrictingPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RedistrictingPlan):
        self.beginResetModel()
        if self._plan:
            self._plan.planChanged.disconnect(self.planChanged)
            self._plan.districts.updateComplete.disconnect(self.statsUpdated)
        self._plan = value
        if self._plan:
            self._plan.planChanged.connect(self.planChanged)
            self._plan.districts.updateComplete.connect(self.statsUpdated)
        self.endResetModel()

    def planChanged(self, plan, prop, value, oldValue):  # pylint: disable=unused-argument
        if prop == 'geo-fields':
            self.beginResetModel()
            self.endResetModel()

    def statsUpdated(self):
        self.beginResetModel()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0

        c = 5
        if self._plan and self._plan.geoFields:
            c += 1 + len(self._plan.geoFields)
        return c

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1 if not parent.isValid() else 0

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal:
            return None

        if role == Qt.DisplayRole:
            return self.StatLabels[section] if section <= 5 else '   ' + self._plan.geoFields[section-6].caption

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if self._plan is None or not index.isValid() or index.column() != 0:
            return None

        row = index.row()
        if role == Qt.DisplayRole:
            if row == 0:
                result = f'{self._plan.totalPopulation:,}'
            elif row == 1:
                avgPP = self._plan.stats.avgPolsbyPopper
                result = f'{avgPP:.3f}' if avgPP is not None else ''
            elif row == 2:
                avgReock = self._plan.stats.avgReock
                result = f'{avgReock:.3f}' if avgReock is not None else ''
            elif row == 3:
                avgCH = self._plan.stats.avgConvexHull
                result = f'{avgCH:.3f}' if avgCH is not None else ''
            elif row == 4:
                result = f'{self._plan.stats.cutEdges:,}' if self._plan.stats.cutEdges else ''
            elif row == 5:
                result = None
            elif row <= 6 + len(self._plan.geoFields):
                result = f'{len(self._plan.stats.splits[self._plan.geoFields[row-6]]):,}'
            else:
                result = None
        elif role == Qt.FontRole:
            result = QFont()
            result.setBold(True)
        else:
            result = None

        return result


class DockDistrictDataTable(Ui_qdwDistrictData, QDockWidget):
    @property
    def plan(self) -> RedistrictingPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RedistrictingPlan):
        self.gbxPlanStats.setContentsMargins(0, 20, 0, 0)
        self._plan = value
        self._model.plan = value
        self._statsModel.plan = value

        if self._plan is None:
            self.btnAddFields.setEnabled(False)
            self.btnRecalculate.setEnabled(False)
            self.lblPlanName.setText(QCoreApplication.translate('Redistricting', 'No plan selected'))
        else:
            self.btnAddFields.setEnabled(True)
            self.btnRecalculate.setEnabled(True)
            self.lblPlanName.setText(self._plan.name)

    def __init__(self, plan: RedistrictingPlan, parent: QObject = None):
        super().__init__(parent)
        self.setupUi(self)

        self.fieldStats: Dict[Field, QWidget] = {}

        self.tblDataTable.installEventFilter(self)
        self.lblWaiting = OverlayWidget(self.tblDataTable)
        self.lblWaiting.setVisible(False)

        self._model = DistrictDataModel(None, self)
        self._model.modelAboutToBeReset.connect(self.lblWaiting.start)
        self._model.modelReset.connect(self.lblWaiting.stop)
        self.tblDataTable.setModel(self._model)

        self._statsModel = StatsModel(plan)
        self.tblPlanStats.setModel(self._statsModel)
        self.tblPlanStats.verticalHeader()
        self.gbxPlanStats.setContentsMargins(0, 20, 0, 0)

        self.btnCopy.setIcon(
            QgsApplication.getThemeIcon('/mActionEditCopy.svg'))
        self.btnCopy.clicked.connect(self.copyToClipboard)
        self.btnRecalculate.setIcon(
            QgsApplication.getThemeIcon('/mActionRefresh.svg'))
        self.btnRecalculate.clicked.connect(self.recalculate)
        self.btnAddFields.setIcon(
            QgsApplication.getThemeIcon('/mActionAddManualTable.svg'))
        self.btnAddFields.clicked.connect(self.addFieldDlg)

        self.btnHelp.setIcon(QgsApplication.getThemeIcon('/mActionHelpContents.svg'))
        self.btnHelp.clicked.connect(self.btnHelpClicked)
        self._plan: RedistrictingPlan = None
        self.plan = plan

    def addFieldDlg(self):
        dlg = DlgEditFields(self._plan)
        dlg.exec_()

    def recalculate(self):
        self._plan.districts.resetData(immediate=True)

    def copyToClipboard(self):
        """Copy district data to clipboard in csv format"""
        m: DistrictDataModel = self.tblDataTable.model()
        t = []
        r = []
        for h in range(0, m.columnCount()):
            r.append(f'"{m.headerData(h, Qt.Horizontal, Qt.DisplayRole)}"')

        t.append(r)
        for row in range(1, self.plan.numDistricts+1):
            r = []
            for col in range(m.columnCount()):
                index = m.index(row, col, QModelIndex())
                v = m.data(index, Qt.DisplayRole)
                v = v if v is not None else ''
                r.append(f'"{v}"')
            t.append(r)

        cb = QgsApplication.instance().clipboard()
        text = os.linesep.join([','.join(r) for r in t])
        cb.setText(text)

    def copySelection(self):
        selection = self.tblDataTable.selectedIndexes()
        if selection:
            rows = sorted(index.row() for index in selection)
            columns = sorted(index.column() for index in selection)
            rowcount = rows[-1] - rows[0] + 1
            colcount = columns[-1] - columns[0] + 1
            table = [[''] * colcount for _ in range(rowcount)]
            for index in selection:
                row = index.row() - rows[0]
                column = index.column() - columns[0]
                table[row][column] = index.data()
            stream = io.StringIO()
            csv.writer(stream, delimiter='\t').writerows(table)
            QgsApplication.instance().clipboard().setText(stream.getvalue())
        return

    def eventFilter(self, source, event):
        if (event.type() == QEvent.KeyPress and
                event.matches(QKeySequence.Copy)):
            self.copySelection()
            return True
        return super().eventFilter(source, event)

    def btnHelpClicked(self):
        showHelp('usage/data_table.html')
