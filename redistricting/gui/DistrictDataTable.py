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
import csv
import io
from typing import (
    Any,
    Dict,
    Optional
)

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import (
    QAbstractTableModel,
    QCoreApplication,
    QMimeData,
    QModelIndex,
    QObject,
    QPoint,
    Qt
)
from qgis.PyQt.QtGui import (
    QColor,
    QContextMenuEvent,
    QFont,
    QKeySequence
)
from qgis.PyQt.QtWidgets import (
    QAction,
    QDockWidget,
    QMenu,
    QWidget
)

from ..models import (
    Field,
    PlanStats,
    RedistrictingPlan
)
from ..services import (
    ActionRegistry,
    DistrictCopier,
    DistrictUpdater
)
from ..utils import (
    showHelp,
    tr
)
from .DistrictDataModel import DistrictDataModel
from .DlgEditFields import DlgEditFields
from .DlgSplits import DlgSplitDetail
from .RdsOverlayWidget import OverlayWidget
from .ui.DistrictDataTable import Ui_qdwDistrictData


class StatsModel(QAbstractTableModel):
    StatLabels = [
        tr('Population'),
        tr('Continguous'),
        tr('Compactness'),
        tr('   Avg. Polsby-Popper'),
        tr('   Avg. Reock'),
        tr('   Avg. Convex-Hull'),
        tr('   Cut Edges'),
        tr('Splits')
    ]
    SPLITS_OFFSET = 8

    def __init__(self, stats: PlanStats, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._stats = None
        self.setStats(stats)

    def setStats(self, value: PlanStats):
        self.beginResetModel()
        if self._stats:
            self._stats.statsUpdating.disconnect(self.beginResetModel)
            self._stats.statsUpdated.disconnect(self.endResetModel)
            for s in self._stats.splits.values():
                s.splitUpdating.disconnect(self.beginResetModel)
                s.splitUpdated.disconnect(self.endResetModel)
        self._stats = value
        if self._stats:
            self._stats.statsUpdating.connect(self.beginResetModel)
            self._stats.statsUpdated.connect(self.endResetModel)
            for s in self._stats.splits.values():
                s.splitUpdating.connect(self.beginResetModel)
                s.splitUpdated.connect(self.endResetModel)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0

        c = StatsModel.SPLITS_OFFSET - 1
        if self._stats:
            c += 1 + len(self._stats.splits)
        return c

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1 if not parent.isValid() else 0

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return StatsModel.StatLabels[section] \
                if section < StatsModel.SPLITS_OFFSET \
                else '   ' + self._stats.splits.headings[section-StatsModel.SPLITS_OFFSET]

        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if self._stats is None or not index.isValid() or index.column() != 0:
            return None

        row = index.row()
        if role == Qt.DisplayRole:
            if row == 0:
                result = f'{self._stats.totalPopulation:,}'
            elif row == 1:
                result = tr('Yes') if self._stats.contiguous else tr('No')
            elif row == 3:
                avgPP = self._stats.avgPolsbyPopper
                result = f'{avgPP:.3f}' if avgPP is not None else ''
            elif row == 4:
                avgReock = self._stats.avgReock
                result = f'{avgReock:.3f}' if avgReock is not None else ''
            elif row == 5:
                avgCH = self._stats.avgConvexHull
                result = f'{avgCH:.3f}' if avgCH is not None else ''
            elif row == 6:
                result = f'{self._stats.cutEdges:,}' if self._stats.cutEdges else ''
            elif row in (2, StatsModel.SPLITS_OFFSET - 1):
                result = None
            elif row <= StatsModel.SPLITS_OFFSET + len(self._stats.splits):
                result = f'{len(self._stats.splits[row-StatsModel.SPLITS_OFFSET]):,}'
            else:
                result = None
        elif role == Qt.FontRole:
            result = QFont()
            result.setBold(True)
        elif role == Qt.TextColorRole:
            if row == 1:
                if not self._stats.contiguous:
                    result = QColor(Qt.red)
                else:
                    result = QColor(Qt.green)
            else:
                result = None
        else:
            result = None

        return result


class DockDistrictDataTable(Ui_qdwDistrictData, QDockWidget):
    def __init__(self, updateService: DistrictUpdater, districtCopier: DistrictCopier, parent: QObject = None):
        super().__init__(parent)
        self.setupUi(self)

        self.districtCopier = districtCopier
        self.updateService = updateService
        self.updateService.updateStarted.connect(self.updateStarted)
        self.updateService.updateComplete.connect(self.updateComplete)
        self.updateService.updateTerminated.connect(self.updateTerminated)

        self.fieldStats: Dict[Field, QWidget] = {}

        self.tblDataTable.installEventFilter(self)
        self.lblWaiting = OverlayWidget(self.tblDataTable)
        self.lblWaiting.setVisible(False)

        self._model = DistrictDataModel(None, self)
        self.tblDataTable.setModel(self._model)

        self._statsModel = StatsModel(None, self)
        self.tblPlanStats.setModel(self._statsModel)
        self.tblPlanStats.verticalHeader()
        self.tblPlanStats.doubleClicked.connect(self.statsDoubleClicked)
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
        self._dlgSplits: DlgSplitDetail = None

        self._plan: RedistrictingPlan = None

        self.actionRegistry = ActionRegistry()

        self.actionCopy = QAction(
            QgsApplication.getThemeIcon('/mActionEditCopy.svg'),
            self.tr("Copy data"),
            self
        )
        self.actionCopy.setToolTip(self.tr("Copy selected demographic data to clipboard"))
        self.actionCopy.triggered.connect(self.copySelection)
        self.actionCopy.setShortcut(QKeySequence.Copy)
        self.addAction(self.actionCopy)

        self.tblDataTable.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tblDataTable.customContextMenuRequested.connect(self.createDataTableConextMenu)

    @property
    def plan(self) -> RedistrictingPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RedistrictingPlan):
        if self._dlgSplits:
            self._dlgSplits.close()
            self._dlgSplits = None

        self.gbxPlanStats.setContentsMargins(0, 20, 0, 0)
        self._plan = value
        self._model.plan = value

        if self._plan is None:
            self.btnAddFields.setEnabled(False)
            self.btnRecalculate.setEnabled(False)
            self.lblPlanName.setText(QCoreApplication.translate('Redistricting', 'No plan selected'))
            self._statsModel.setStats(None)
        else:
            self._plan.nameChanged.connect(self.planChanged)
            self.btnAddFields.setEnabled(True)
            self.btnRecalculate.setEnabled(True)
            self.lblPlanName.setText(self._plan.name)
            self._statsModel.setStats(self._plan.stats)

    def planChanged(self, name):
        self.lblPlanName.setText(name)

    def updateStarted(self, plan: RedistrictingPlan):
        if plan == self._plan:
            self.lblWaiting.start()

    def updateComplete(self, plan: RedistrictingPlan, districts: Optional[set[int]] = None):
        if plan == self._plan:
            self.lblWaiting.stop()
            self._model.districtsUpdated(districts)

    def updateTerminated(self, plan: RedistrictingPlan):
        if plan == self._plan:
            self.lblWaiting.stop()

    def addFieldDlg(self):
        dlg = DlgEditFields(self._plan)
        dlg.exec_()

    def recalculate(self):
        self.updateService.updateDistricts(self._plan, needDemographics=True, needSplits=True)

    def copyMimeDataToClipboard(self, selection: Optional[list[QModelIndex]] = None):
        """Copy district data to clipboard in html table format"""
        if selection:
            selection = ((s.row(), s.column()) for s in selection)
        html = self._plan.districts.getAsHtml(selection)
        text = self._plan.districts.getAsCsv(selection)
        mime = QMimeData()
        mime.setHtml(html)
        mime.setData("application/csv", text.encode())
        QgsApplication.instance().clipboard().setMimeData(mime)

    def copyToClipboard(self):
        self.copyMimeDataToClipboard()

    def copySelection(self):
        table = None
        if self.tblPlanStats.hasFocus():
            selection = self.tblPlanStats.selectedIndexes()
            if selection:
                selection.sort(key=lambda idx: idx.row())
                table = []
                for idx in selection:
                    table.append([self._statsModel.headerData(idx.row(), Qt.Vertical, Qt.DisplayRole), idx.data()])
                stream = io.StringIO()
                csv.writer(stream, delimiter='\t').writerows(table)
                QgsApplication.instance().clipboard().setText(stream.getvalue())
        else:
            selection = self.tblDataTable.selectedIndexes()
            if selection:
                self.copyMimeDataToClipboard(selection)

    def contextMenuEvent(self, event: QContextMenuEvent):
        menu = QMenu(self)
        menu.addActions(self.actions())
        menu.exec(event.globalPos())

    def createDataTableConextMenu(self, pos: QPoint):
        menu = QMenu(self)
        menu.addAction(self.actionCopy)

        idx = self.tblDataTable.indexAt(pos)
        district = self._plan.districts[idx.row()]

        menu.addAction(self.actionRegistry.actionCopyDistrict)
        self.actionRegistry.actionCopyDistrict.setData(district.district)
        self.actionRegistry.actionCopyDistrict.setEnabled(district.district != 0)
        menu.addAction(self.actionRegistry.actionPasteDistrict)
        self.actionRegistry.actionPasteDistrict.setData(district.district)
        self.actionRegistry.actionPasteDistrict.setEnabled(self.districtCopier.canPasteAssignments(self._plan))
        menu.addAction(self.actionRegistry.actionZoomToDistrict)
        self.actionRegistry.actionZoomToDistrict.setData(district.district)
        menu.addAction(self.actionRegistry.actionFlashDistrict)
        self.actionRegistry.actionFlashDistrict.setData(district.district)
        self.actionRegistry.actionFlashDistrict.setEnabled(district.district != 0)
        menu.exec(self.tblDataTable.mapToGlobal(pos))

    def btnHelpClicked(self):
        showHelp('usage/data_table.html')

    def statsDoubleClicked(self, index: QModelIndex):
        row = index.row()
        if row >= 6:
            field = self._plan.geoFields[row-6]
            if self._dlgSplits:
                self._dlgSplits.geoField = field
            else:
                self._dlgSplits = DlgSplitDetail(self._plan, field, self.parent())
            self._dlgSplits.show()
