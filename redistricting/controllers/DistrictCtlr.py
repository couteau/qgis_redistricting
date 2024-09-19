"""QGIS Redistricting Plugin - district-related actions

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
import csv
import io
from typing import (
    TYPE_CHECKING,
    Optional,
    Union
)

from qgis.core import (
    QgsApplication,
    QgsProject
)
from qgis.gui import (
    QgisInterface,
    QgsMapMouseEvent
)
from qgis.PyQt.QtCore import (
    QEvent,
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
    QMenu,
    QToolBar
)

from ..gui import (
    DockDistrictDataTable,
    TableViewKeyEventFilter
)
from ..models import RdsPlan
from ..services import (
    ActionRegistry,
    AssignmentsService,
    DistrictClipboardAccess,
    DistrictCopier,
    DistrictUpdater,
    PlanManager,
    RdsDistrictDataModel,
    RdsDistrictFilterFieldsProxyModel,
    RdsPlanMetricsModel
)
from ..utils import tr
from .BaseCtlr import BaseController

if TYPE_CHECKING:
    from PyQt5.QtWidgets import QAction
else:
    from qgis.PyQt.QtWidgets import QAction


class DistrictController(BaseController):
    def __init__(
        self,
        iface: QgisInterface,
        project: QgsProject,
        planManager: PlanManager,
        toolbar: QToolBar,
        assignmentsService: AssignmentsService,
        districtCopier: DistrictCopier,
        updateService: DistrictUpdater,
        parent: Optional[QObject] = None
    ):
        super().__init__(iface, project, planManager, toolbar, parent)
        self.canvas = iface.mapCanvas()
        self.assignmentsService = assignmentsService
        self.districtCopier = districtCopier
        self.updateService = updateService
        self.actionToggle: QAction = None
        self.model: RdsDistrictDataModel = None
        self.proxyModel: RdsDistrictFilterFieldsProxyModel = None
        self.metricsModel: RdsPlanMetricsModel = None
        self.dockwidget: DockDistrictDataTable = None
        self.actions = ActionRegistry()

        self.actionCopyDistrict = self.actions.createAction(
            name='actionCopyDistrict',
            icon=':/plugins/redistricting/copydistrict.svg',
            text=str('Copy District'),
            tooltip=tr('Copy district to clipboard'),
            callback=self.districtCopier.copyDistrict,
            parent=self.iface.mainWindow()
        )

        self.actionPasteDistrict = self.actions.createAction(
            name='actionPasteDistrict',
            icon=QgsApplication.getThemeIcon('/mActionDuplicateFeature.svg'),
            text=tr('Paste District'),
            tooltip=tr('Paste district from clipboard'),
            callback=self.districtCopier.pasteDistrict,
            parent=self.iface.mainWindow()
        )

        self.actionZoomToDistrict = self.actions.createAction(
            name="actionZoomToDistrict",
            icon=':/plugins/redistricting/zoomdistrict.svg',
            text=tr("Zoom to District"),
            callback=self.zoomToDistrict,
            parent=self.iface.mainWindow()
        )

        self.actionFlashDistrict = self.actions.createAction(
            name='actionFlashDistrict',
            icon=':/plugins/redistricting/flashdistrict.svg',
            text=self.tr("Flash District"),
            callback=self.flashDistrict,
            parent=self.iface.mainWindow()
        )

        self.actionCopyDistrictData = self.actions.createAction(
            name="actionCopyDistrictsData",
            icon=QgsApplication.getThemeIcon('/mActionEditCopy.svg'),
            text=self.tr("Copy Data"),
            tooltip=self.tr("Copy selected demographic data to clipboard"),
            callback=self.copySelection,
            shortcut=QKeySequence.Copy,
            parent=self.iface.mainWindow()
        )

        self.actionRecalculate = self.actions.createAction(
            name="actionRecalculate",
            icon=QgsApplication.getThemeIcon('/mActionRefresh.svg'),
            text=self.tr("Recalculate"),
            tooltip=self.tr("Recalculate"),
            statustip=self.tr("Reaggregate all demographics"),
            callback=self.recalculate
        )

        self.actionToggleMetrics: QAction = None

        self.dataTableContextMenu = QMenu()
        self.dataTableContextMenu.addAction(self.actionCopyDistrictData)
        self.dataTableContextMenu.addAction(self.actionCopyDistrict)
        self.dataTableContextMenu.addAction(self.actionPasteDistrict)
        self.dataTableContextMenu.addAction(self.actionZoomToDistrict)
        self.dataTableContextMenu.addAction(self.actionFlashDistrict)

    def load(self):
        self.createDataTableDockWidget()
        self.planManager.activePlanChanged.connect(self.activePlanChanged)
        self.updateService.updateStarted.connect(self.showOverlay)
        self.updateService.updateComplete.connect(self.hideOverlay)
        self.updateService.updateTerminated.connect(self.hideOverlay)
        self.canvas.contextMenuAboutToShow.connect(self.addCanvasContextMenuItems)

    def unload(self):
        self.canvas.contextMenuAboutToShow.disconnect(self.addCanvasContextMenuItems)
        self.updateService.updateStarted.disconnect(self.showOverlay)
        self.updateService.updateComplete.disconnect(self.hideOverlay)
        self.updateService.updateTerminated.disconnect(self.hideOverlay)
        self.planManager.activePlanChanged.disconnect(self.activePlanChanged)
        self.iface.removeDockWidget(self.dockwidget)
        self.dockwidget.destroy()
        self.dockwidget = None
        self.metricsModel = None

    def createDataTableDockWidget(self):
        """Create the dockwidget that displays district statistics and wire up the interface."""
        self.model = RdsDistrictDataModel()
        self.proxyModel = RdsDistrictFilterFieldsProxyModel()
        self.proxyModel.setSourceModel(self.model)
        self.proxyModel.setSortRole(RdsDistrictDataModel.RawDataRole)
        self.updateService.updateComplete.connect(self.model.districtsUpdated)

        self.metricsModel = RdsPlanMetricsModel(None)

        dockwidget = DockDistrictDataTable()
        dockwidget.installEventFilter(self)
        dockwidget.tblDataTable.activated.connect(self.editDistrict)
        dockwidget.tblDataTable.setContextMenuPolicy(Qt.CustomContextMenu)
        dockwidget.tblDataTable.customContextMenuRequested.connect(self.createDataTableContextMenu)
        dockwidget.tblDataTable.setModel(self.proxyModel)
        dockwidget.tblPlanMetrics.setModel(self.metricsModel)
        dockwidget.tblPlanMetrics.installEventFilter(TableViewKeyEventFilter(dockwidget))
        dockwidget.tblPlanMetrics.activated.connect(self.showMetricsDetail)
        dockwidget.btnCopy.setDefaultAction(self.actionCopyDistrictData)
        dockwidget.btnRecalculate.setDefaultAction(self.actionRecalculate)
        dockwidget.btnDemographics.toggled.connect(self.proxyModel.showDemographics)
        dockwidget.btnMetrics.toggled.connect(self.proxyModel.showMetrics)
        self.iface.addDockWidget(Qt.BottomDockWidgetArea, dockwidget)

        self.actionToggle = dockwidget.toggleViewAction()
        self.actionToggle.setIcon(QgsApplication.getThemeIcon('/mActionOpenTable.svg'))
        self.actionToggle.setText(tr('District Data'))
        self.actionToggle.setToolTip(tr('Show/hide district demographic data/metrics table'))
        self.actions.registerAction('actionToggleDataTable', self.actionToggle)
        self.toolbar.addAction(self.actionToggle)

        self.actionToggleMetrics = self.actions.createAction(
            'actionToggleMetrics',
            ':/plugins/redistricting/planmetrics.svg',
            'Plan metrics',
            'Show/hide plan metrics',
            checkable=True,
            callback=dockwidget.gbxPlanMetrics.setVisible
        )
        self.actionToggleMetrics.setChecked(True)
        dockwidget.btnPlanMetrics.setDefaultAction(self.actionToggleMetrics)

        self.dockwidget = dockwidget
        return self.dockwidget

    def activePlanChanged(self, plan: Union[RdsPlan, None]):
        self.dockwidget.setWaiting(False)
        self.model.plan = plan
        if plan is not None:
            self.metricsModel.setMetrics(plan.metrics)
        else:
            self.metricsModel.setMetrics(None)
        self.dockwidget.plan = plan
        self.actionRecalculate.setEnabled(plan is not None)
        self.actionCopyDistrictData.setEnabled(plan is not None)
        if self.updateService.planIsUpdating(plan):
            self.dockwidget.setWaiting(True)

    def addCanvasContextMenuItems(self, menu: QMenu, event: QgsMapMouseEvent):
        if self.planManager.activePlan is None:
            return

        menu.addAction(self.actionCopyDistrict)
        self.actionCopyDistrict.setEnabled(self.districtCopier.canCopyAssignments(self.actionCopyDistrict, event))

        menu.addAction(self.actionPasteDistrict)
        self.actionPasteDistrict.setEnabled(self.districtCopier.canPasteAssignments(self.planManager.activePlan))

    def eventFilter(self, obj: QObject, event: QContextMenuEvent):  # pylint: disable=unused-argument
        if event.type() != QEvent.ContextMenu:
            return False

        menu = QMenu()
        menu.addActions([self.actionCopyDistrict, self.actionPasteDistrict,
                        self.actionZoomToDistrict, self.actionFlashDistrict])
        menu.exec(event.globalPos())

        return True

    def createDataTableContextMenu(self, pos: QPoint):
        idx = self.dockwidget.tblDataTable.indexAt(pos)
        if self.activePlan is None:
            return

        district = self.planManager.activePlan.districts[idx.row()]
        self.actionCopyDistrict.setData(district.district)
        self.actionCopyDistrict.setEnabled(district.district != 0)
        self.actionPasteDistrict.setData(district.district)
        self.actionPasteDistrict.setEnabled(self.districtCopier.canPasteAssignments(self.planManager.activePlan))
        self.actionZoomToDistrict.setData(district.district)
        self.actionFlashDistrict.setData(district.district)
        self.actionFlashDistrict.setEnabled(district.district != 0)

        self.dataTableContextMenu.exec(self.dockwidget.tblDataTable.mapToGlobal(pos))

    def districtAction(self, district, method, refresh):
        if self.planManager.activePlan is None:
            return

        if isinstance(district, bool):
            district = None

        if district is None:
            action = self.sender()
            if isinstance(action, QAction):
                district = action.data()

        if not isinstance(district, int):
            raise TypeError()

        if district < 1 or district > self.planManager.activePlan.numDistricts:
            raise ValueError()

        fid = self.planManager.activePlan.districts[district].fid
        if fid != -1:
            method(self.planManager.activePlan.distLayer, [fid])
            if refresh:
                self.canvas.refresh()

    def zoomToDistrict(self, district: Optional[int]):
        self.districtAction(district, self.canvas.zoomToFeatureIds, True)

    def flashDistrict(self, district: Optional[int]):
        self.districtAction(district, self.canvas.flashFeatureIds, False)

    def copyMimeDataToClipboard(self, selection: Optional[list[QModelIndex]] = None):
        """Copy district data to clipboard in html table format"""
        if selection:
            selection = ((s.row(), s.column()) for s in selection)

        clipboard = DistrictClipboardAccess()
        html = clipboard.getAsHtml(self.planManager.activePlan, selection)
        text = clipboard.getAsCsv(self.planManager.activePlan, selection)
        mime = QMimeData()
        mime.setHtml(html)
        mime.setData("application/csv", text.encode())
        QgsApplication.instance().clipboard().setMimeData(mime)

    def copyToClipboard(self):
        self.copyMimeDataToClipboard()

    def copySelection(self):
        table = None
        if self.dockwidget.tblPlanStats.hasFocus():
            selection = self.dockwidget.tblPlanStats.selectedIndexes()
            if selection:
                selection.sort(key=lambda idx: idx.row())
                table = []
                for idx in selection:
                    table.append([self.metricsModel.headerData(
                        idx.row(), Qt.Vertical, Qt.DisplayRole), idx.data()])
                stream = io.StringIO()
                csv.writer(stream, delimiter='\t').writerows(table)
                QgsApplication.instance().clipboard().setText(stream.getvalue())
        else:
            selection = self.dockwidget.tblDataTable.selectedIndexes()
            if selection:
                self.copyMimeDataToClipboard(selection)

    def recalculate(self):
        self.updateService.updateDistricts(self.planManager.activePlan, needDemographics=True, needSplits=True)

    def editDistrict(self, index: QModelIndex):
        if not self.actions.actionEditDistrict.isEnabled():
            return

        if index.row() == 0:
            return

        district = self.planManager.activePlan.districts[index.row()]
        self.actions.actionEditDistrict.setData(district)
        self.actions.actionEditDistrict.trigger()

    def showMetricsDetail(self, index: QModelIndex):
        row = index.row()
        if row == 1:
            if not self.actions.actionShowSplitDistrictsDialog.isEnabled():
                return
            self.actions.actionShowSplitDistrictsDialog.trigger()
        elif row == 2:
            if not self.actions.actionShowUnassignedGeographyDialog.isEnabled():
                return
            self.actions.actionShowUnassignedGeographyDialog.trigger()
        elif row >= self.metricsModel.SPLITS_OFFSET:
            if not self.actions.actionShowSplitsDialog.isEnabled():
                return
            field = self.planManager.activePlan.geoFields[row-self.metricsModel.SPLITS_OFFSET]
            self.actions.actionShowSplitsDialog.setData(field)
            self.actions.actionShowSplitsDialog.trigger()

    def showOverlay(self, plan: RdsPlan):
        if plan == self.activePlan:
            self.dockwidget.setWaiting(True)

    def hideOverlay(self, plan: RdsPlan):
        if plan == self.activePlan:
            self.dockwidget.setWaiting(False)
