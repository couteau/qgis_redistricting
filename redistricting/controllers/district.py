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

from ..gui import DockDistrictDataTable
from ..models import (
    RdsDistrictDataModel,
    RdsDistrictFilterFieldsProxyModel,
    RdsPlan
)
from ..services import (
    ActionRegistry,
    AssignmentsService,
    DistrictClipboardAccess,
    DistrictCopier,
    DistrictUpdater,
    PlanManager
)
from ..utils import tr
from .base import DockWidgetController

if TYPE_CHECKING:
    from qgis.PyQt.QtCore import QT_VERSION
    if QT_VERSION >= 0x060000:
        from PyQt6.QtGui import QAction  # type: ignore[import]
    else:
        from PyQt5.QtWidgets import QAction  # type: ignore[import]

else:
    from qgis.PyQt.QtGui import QAction


class DistrictController(DockWidgetController):
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
        self.model: RdsDistrictDataModel = None
        self.proxyModel: RdsDistrictFilterFieldsProxyModel = None
        self.actions = ActionRegistry()

        self.dockwidget: DockDistrictDataTable

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
            name="actionCopyDistrictData",
            icon=QgsApplication.getThemeIcon('/mActionEditCopy.svg'),
            text=self.tr("Copy Data"),
            tooltip=self.tr("Copy demographic data to clipboard"),
            callback=self.copyToClipboard,
            parent=self.iface.mainWindow()
        )

        self.actionCopySelectedData = self.actions.createAction(
            name="actionCopySelectedData",
            icon=QgsApplication.getThemeIcon('/mActionEditCopy.svg'),
            text=self.tr("Copy Data"),
            tooltip=self.tr("Copy selected demographic data to clipboard"),
            callback=self.copySelection,
            shortcut=QKeySequence.StandardKey.Copy,
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

        self.dataTableContextMenu: QMenu = None

    def load(self):
        super().load()
        self.dataTableContextMenu = QMenu()
        self.dataTableContextMenu.addAction(self.actionCopySelectedData)
        self.dataTableContextMenu.addAction(self.actionCopyDistrict)
        self.dataTableContextMenu.addAction(self.actionPasteDistrict)
        self.dataTableContextMenu.addAction(self.actionZoomToDistrict)
        self.dataTableContextMenu.addAction(self.actionFlashDistrict)

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
        super().unload()
        self.dataTableContextMenu.destroy(True, True)
        self.dataTableContextMenu = None
        self.model = None
        self.proxyModel = None

    def createDockWidget(self):
        """Create the dockwidget that displays district statistics and wire up the interface."""
        self.model = RdsDistrictDataModel()
        self.proxyModel = RdsDistrictFilterFieldsProxyModel()
        self.proxyModel.setSourceModel(self.model)
        self.proxyModel.setSortRole(RdsDistrictDataModel.RawDataRole)
        self.updateService.updateComplete.connect(self.model.districtsUpdated)

        dockwidget = DockDistrictDataTable()
        dockwidget.installEventFilter(self)
        dockwidget.tblDataTable.activated.connect(self.editDistrict)
        dockwidget.tblDataTable.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        dockwidget.tblDataTable.customContextMenuRequested.connect(self.prepareDataTableContextMenu)
        dockwidget.tblDataTable.setModel(self.proxyModel)
        dockwidget.btnCopy.setDefaultAction(self.actionCopyDistrictData)
        dockwidget.btnRecalculate.setDefaultAction(self.actionRecalculate)
        dockwidget.btnDemographics.toggled.connect(self.proxyModel.showDemographics)
        dockwidget.btnMetrics.toggled.connect(self.proxyModel.showMetrics)

        return dockwidget

    def createToggleAction(self) -> QAction:
        action = super().createToggleAction()
        if action is not None:
            action.setIcon(QgsApplication.getThemeIcon('/mActionOpenTable.svg'))
            action.setText(tr('District Data'))
            action.setToolTip(tr('Show/hide district demographic data/metrics table'))

        return action

    def activePlanChanged(self, plan: Union[RdsPlan, None]):
        self.dockwidget.setWaiting(False)
        self.model.plan = plan
        self.dockwidget.plan = plan
        self.actionRecalculate.setEnabled(plan is not None)
        self.actionCopySelectedData.setEnabled(plan is not None)
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
        if event.type() != QEvent.Type.ContextMenu:
            return False

        menu = QMenu()
        menu.addActions([self.actionCopyDistrict, self.actionPasteDistrict,
                        self.actionZoomToDistrict, self.actionFlashDistrict])
        menu.exec(event.globalPos())

        return True

    def prepareDataTableContextMenu(self, pos: QPoint):
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

    def showOverlay(self, plan: RdsPlan):
        if plan == self.activePlan:
            self.dockwidget.setWaiting(True)

    def hideOverlay(self, plan: RdsPlan):
        if plan == self.activePlan:
            self.dockwidget.setWaiting(False)
