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
    Dict,
    Optional
)

from qgis.core import (
    QgsApplication,
    QgsProject
)
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QMimeData,
    QModelIndex,
    QObject,
    QPoint,
    Qt
)
from qgis.PyQt.QtGui import (
    QContextMenuEvent,
    QKeySequence
)
from qgis.PyQt.QtWidgets import (
    QAction,
    QDialog,
    QDockWidget,
    QMenu,
    QWidget
)

from ..models import (
    RdsField,
    RdsPlan
)
from ..services import (
    ActionRegistry,
    DistrictCopier,
    DistrictUpdater
)
from ..services.clipboard import DistrictClipboardAccess
from ..utils import (
    showHelp,
    tr
)
from .DistrictDataModel import DistrictDataModel
from .DlgEditFields import DlgEditFields
from .DlgNewDistrict import DlgNewDistrict
from .DlgSplits import DlgSplitDetail
from .RdsOverlayWidget import OverlayWidget
from .StatsModel import RdsPlanMetricsModel
from .ui.DistrictDataTable import Ui_qdwDistrictData


class DockDistrictDataTable(Ui_qdwDistrictData, QDockWidget):
    def __init__(self, updateService: DistrictUpdater, districtCopier: DistrictCopier, parent: QObject = None):
        super().__init__(parent)
        self.setupUi(self)

        self.districtCopier = districtCopier
        self.updateService = updateService
        self.updateService.updateStarted.connect(self.updateStarted)
        self.updateService.updateComplete.connect(self.updateComplete)
        self.updateService.updateTerminated.connect(self.updateTerminated)

        self.fieldStats: Dict[RdsField, QWidget] = {}

        self.tblDataTable.installEventFilter(self)
        self.lblWaiting = OverlayWidget(self.tblDataTable)
        self.lblWaiting.setVisible(False)

        self._model = DistrictDataModel(None, self)
        self.tblDataTable.setModel(self._model)

        self._statsModel = RdsPlanMetricsModel(None, self)
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

        self._plan: RdsPlan = None

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
        self.tblDataTable.doubleClicked.connect(self.editDistrict)

    @property
    def plan(self) -> RdsPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RdsPlan):
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
            self._statsModel.setStats(self._plan.metrics)

    def planChanged(self, name):
        self.lblPlanName.setText(name)

    def updateStarted(self, plan: RdsPlan):
        if plan == self._plan:
            self.lblWaiting.start()

    def updateComplete(self, plan: RdsPlan, districts: Optional[set[int]] = None):
        if plan == self._plan:
            self.lblWaiting.stop()
            self._model.districtsUpdated(districts)

    def updateTerminated(self, plan: RdsPlan):
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

        clipboard = DistrictClipboardAccess()
        html = clipboard.getAsHtml(self._plan, selection)
        text = clipboard.getAsCsv(self._plan, selection)
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
            field = self._plan.geoFields[row-self._statsModel.SPLITS_OFFSET]
            if self._dlgSplits:
                self._dlgSplits.geoField = field
            else:
                self._dlgSplits = DlgSplitDetail(self._plan, field, self.parent())
            self._dlgSplits.show()

    def editDistrict(self, index: QModelIndex):
        if index.row() == 0:
            return

        district = self._plan.districts[index.row()]
        dlg = DlgNewDistrict(self.plan, self.parent())
        dlg.setWindowTitle(tr("Edit District"))
        dlg.sbxDistrictNo.setValue(district.district)
        dlg.sbxDistrictNo.setReadOnly(True)
        dlg.inpName.setText(district.name)
        dlg.sbxMembers.setValue(district.members)
        dlg.txtDescription.setPlainText(district.description)
        if dlg.exec() == QDialog.Accepted:
            district.name = dlg.districtName
            district.members = dlg.members
            district.description = dlg.description
            QgsProject.instance().setDirty()
