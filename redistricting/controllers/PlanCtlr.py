"""QGIS Redistricting Plugin - actions for creating/manipualting plans

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
import pathlib
from typing import Optional

from qgis.core import (
    QgsProject,
    QgsVectorLayer
)
from qgis.gui import (
    Qgis,
    QgisInterface
)
from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QActionGroup,
    QDialog,
    QMenu,
    QToolBar,
    QToolButton
)

from ..gui import (
    DlgConfirmDelete,
    DlgCopyPlan,
    DlgEditPlan,
    DlgExportPlan,
    DlgImportPlan,
    DlgImportShape,
    DlgSelectPlan
)
from ..models import RedistrictingPlan
from ..services import (
    ActionRegistry,
    AssignmentImporter,
    DistrictUpdater,
    LayerTreeManager,
    PlanBuilder,
    PlanCopier,
    PlanEditor,
    PlanExporter,
    PlanManager,
    PlanStylerService,
    ShapefileImporter
)
from ..utils import tr
from .BaseCtlr import BaseController


class PlanController(BaseController):
    def __init__(
        self,
        iface: QgisInterface,
        project: QgsProject,
        planManager: PlanManager,
        toolbar: QToolBar,
        layerTreeManager: LayerTreeManager,
        planStyler: PlanStylerService,
        updateService: DistrictUpdater,
        parent: Optional[QObject] = None
    ):
        super().__init__(iface, project, planManager, toolbar, parent)
        self.layerTreeManager = layerTreeManager
        self.styler = planStyler
        self.updateService = updateService

        self.icon = QIcon(':/plugins/redistricting/icon.png')
        self.menuName = tr('&Redistricting')

        self.menu = QMenu(self.menuName, self.iface.mainWindow())
        self.menu.setIcon(self.icon)

        self.menuButton = QToolButton(self.iface.mainWindow())
        self.menuButton.setMenu(self.menu)
        self.menuButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.menuButton.setIcon(self.icon)
        self.menuButton.setToolTip(tr('Redistricting Utilities'))

        self.toolBtnAction = self.toolbar.addWidget(self.menuButton)

        self.planMenu = self.menu.addMenu(self.icon, tr('&Redistricting Plans'))
        self.planActions = QActionGroup(self.iface.mainWindow())

        self.actions = ActionRegistry()

        self.createActions()

    def load(self):
        self.planManager.activePlanChanged.connect(self.enableActivePlanActions)
        self.planManager.planAdded.connect(self.addPlanToMenu)
        self.planManager.planRemoved.connect(self.removePlanFromMenu)
        self.project.layersAdded.connect(self.enableNewPlan)
        self.project.layersRemoved.connect(self.enableNewPlan)
        self.project.cleared.connect(self.clearPlanMenu)

        m: QMenu = self.iface.vectorMenu().addMenu(self.menuName)
        m.addMenu(self.menuButton.menu())

    def unload(self):
        self.planManager.activePlanChanged.disconnect(self.enableActivePlanActions)
        self.planManager.planAdded.disconnect(self.addPlanToMenu)
        self.planManager.planRemoved.disconnect(self.removePlanFromMenu)
        self.project.layersAdded.disconnect(self.enableNewPlan)
        self.project.layersRemoved.disconnect(self.enableNewPlan)
        self.project.cleared.disconnect(self.clearPlanMenu)

    def createActions(self):
        self.actionShowPlanManager = self.actions.createAction(
            'actionShowPlanManager',
            QIcon(':/plugins/redistricting/planmanager.svg'),
            tr('Plan Manager'),
            callback=self.showPlanManager,
            parent=self.iface.mainWindow()
        )
        self.menu.addAction(self.actionShowPlanManager)
        self.menuButton.clicked.connect(self.actionShowPlanManager.trigger)

        self.actionNewPlan = self.actions.createAction(
            'actionNewPlan',
            QIcon(':/plugins/redistricting/addplan.svg'),
            tr('New Redistricting Plan'),
            tooltip=tr('Create a new redistricting plan'),
            callback=self.newPlan,
            parent=self.iface.mainWindow()
        )
        self.actionNewPlan.setEnabled(False)
        self.menu.addAction(self.actionNewPlan)

        self.actionEditPlan = self.actions.createAction(
            'actionEditPlan',
            QIcon(':/plugins/redistricting/icon.png'),
            tr('Edit Plan'),
            callback=self.editPlan,
            parent=self.iface.mainWindow()
        )
        self.actionEditPlan.setEnabled(False)
        self.menu.addAction(self.actionEditPlan)

        self.actionCopyPlan = self.actions.createAction(
            'actionCopyPlan',
            QIcon(':/plugins/redistricting/copyplan.svg'),
            tr('Copy Plan'),
            tooltip=tr('Copy the active plan to a new redistricting plan'),
            callback=self.copyPlan,
            parent=self.iface.mainWindow()
        )
        self.actionCopyPlan.setEnabled(False)
        self.menu.addAction(self.actionCopyPlan)

        self.actionImportAssignments = self.actions.createAction(
            'actionImportAssignments',
            QIcon(':/plugins/redistricting/importplan.svg'),
            tr('Import Equivalency File'),
            tooltip=tr('Import equivalency file to district field'),
            callback=self.importPlan,
            parent=self.iface.mainWindow()
        )
        self.actionImportAssignments.setEnabled(False)
        self.menu.addAction(self.actionImportAssignments)

        self.actionImportShapefile = self.actions.createAction(
            'actionImportShapefile',
            QIcon(':/plugins/redistricting/importplan.svg'),
            tr('Import Shapefile'),
            tooltip=tr('Import assignments from sahpefile'),
            callback=self.importShapefile,
            parent=self.iface.mainWindow()
        )
        self.actionImportShapefile.setEnabled(False)
        self.menu.addAction(self.actionImportShapefile)

        self.actionExportPlan = self.actions.createAction(
            'actionExportPlan',
            QIcon(':/plugins/redistricting/exportplan.svg'),
            tr('Export Plan'),
            tooltip=tr('Export plan as equivalency and/or shapefile'),
            callback=self.exportPlan,
            parent=self.iface.mainWindow()
        )
        self.actionExportPlan.setEnabled(False)
        self.menu.addAction(self.actionExportPlan)

    # slots

    def enableActivePlanActions(self, plan: RedistrictingPlan):
        self.actionEditPlan.setEnabled(plan is not None)
        self.actionCopyPlan.setEnabled(plan is not None and plan.isValid())
        self.actionImportAssignments.setEnabled(plan is not None and plan.isValid())
        self.actionImportShapefile.setEnabled(plan is not None and plan.isValid())
        self.actionExportPlan.setEnabled(
            plan is not None and plan.assignLayer is not None and plan.distLayer is not None
        )

        if plan is not None:
            action = self.planActions.findChild(QAction, plan.name)
            if action:
                action.setChecked(True)

            self.layerTreeManager.bringPlanToTop(plan)
        else:
            self.planActions.checkedAction().setChecked(False)

    def enableNewPlan(self):
        self.actionNewPlan.setEnabled(
            any(isinstance(layer, QgsVectorLayer)for layer in self.project.mapLayers(True).values())
        )

    def clearPlanMenu(self):
        self.planMenu.clear()
        del self.planActions
        self.planActions = QActionGroup(self.iface.mainWindow())
        self.actionNewPlan.setEnabled(
            any(isinstance(layer, QgsVectorLayer)
                for layer in self.project.mapLayers(True).values())
        )

    def addPlanToMenu(self, plan: RedistrictingPlan):
        action = QAction(text=plan.name, parent=self.planActions)
        action.setObjectName(plan.name)
        action.setToolTip(plan.description)
        action.setCheckable(True)
        action.setData(plan)
        action.triggered.connect(self.activatePlan)
        self.planMenu.addAction(action)

    def removePlanFromMenu(self, plan: RedistrictingPlan):
        action = self.planActions.findChild(QAction, plan.name)
        if action:
            action.triggered.disconnect(self.activatePlan)
            self.planMenu.removeAction(action)
            self.planActions.removeAction(action)

    # action slots

    def showPlanManager(self):
        """Display the plan manager window"""
        dlg = DlgSelectPlan(self.planManager, self.iface.mainWindow())
        dlg.newPlan.connect(self.newPlan)
        dlg.planSelected.connect(self.selectPlan)
        dlg.planEdited.connect(self.editPlan)
        dlg.planDeleted.connect(self.deletePlan)
        dlg.exec()

    def newPlan(self):
        """Display new redistricting plan dialog and create new plan"""
        if len(self.project.mapLayers()) == 0:
            self.iface.messageBar().pushMessage(
                tr("Oops!"),
                tr("Cannot create a redistricting plan for an "
                   "empty project. Try adding some layers."),
                level=Qgis.Warning,
                duration=5)
            return

        dlgNewPlan = DlgEditPlan(parent=self.iface.mainWindow())
        if dlgNewPlan.exec() == QDialog.Accepted:
            builder = PlanBuilder() \
                .setName(dlgNewPlan.planName()) \
                .setNumDistricts(dlgNewPlan.numDistricts()) \
                .setNumSeats(dlgNewPlan.numSeats()) \
                .setDescription(dlgNewPlan.description()) \
                .setDeviation(dlgNewPlan.deviation()) \
                .setGeoIdField(dlgNewPlan.geoIdField()) \
                .setGeoDisplay(dlgNewPlan.geoIdCaption()) \
                .setGeoLayer(dlgNewPlan.geoLayer()) \
                .setPopLayer(dlgNewPlan.popLayer()) \
                .setPopJoinField(dlgNewPlan.joinField()) \
                .setPopField(dlgNewPlan.popField()) \
                .setPopFields(dlgNewPlan.popFields()) \
                .setDataFields(dlgNewPlan.dataFields()) \
                .setGeoFields(dlgNewPlan.geoFields()) \
                .setGeoPackagePath(dlgNewPlan.gpkgPath())

            if dlgNewPlan.importPlan():
                importer = AssignmentImporter(self.iface) \
                    .setSourceFile(dlgNewPlan.importPath()) \
                    .setJoinField(dlgNewPlan.importField()) \
                    .setHeaderRow(dlgNewPlan.importHeaderRow()) \
                    .setDelimiter(dlgNewPlan.importDelim()) \
                    .setQuoteChar(dlgNewPlan.importQuote()) \
                    .setGeoColumn(dlgNewPlan.importGeoCol()) \
                    .setDistColumn(dlgNewPlan.importDistCol())
            else:
                importer = None

            self.buildPlan(builder, importer)

    def editPlan(self, plan=None):
        """Open redistricting plan in the edit dialog"""
        if not isinstance(plan, RedistrictingPlan):
            plan = self.planManager.activePlan
        if not plan:
            return

        dlgEditPlan = DlgEditPlan(plan, self.iface.mainWindow())
        if dlgEditPlan.exec() == QDialog.Accepted:
            builder = PlanEditor.fromPlan(plan) \
                .setName(dlgEditPlan.planName()) \
                .setNumDistricts(dlgEditPlan.numDistricts()) \
                .setNumSeats(dlgEditPlan.numSeats()) \
                .setDescription(dlgEditPlan.description()) \
                .setDeviation(dlgEditPlan.deviation()) \
                .setGeoDisplay(dlgEditPlan.geoIdCaption()) \
                .setPopLayer(dlgEditPlan.popLayer()) \
                .setPopField(dlgEditPlan.popField()) \
                .setPopFields(dlgEditPlan.popFields()) \
                .setDataFields(dlgEditPlan.dataFields()) \
                .setGeoFields(dlgEditPlan.geoFields())

            if builder.updatePlan():
                self.project.setDirty()
                if 'num-districts' in builder.modifiedFields:
                    self.styler.stylePlan(plan)

    def copyPlan(self):
        if not self.checkActivePlan(tr('copy')):
            return

        dlgCopyPlan = DlgCopyPlan(self.planManager.activePlan, self.iface.mainWindow())
        if dlgCopyPlan.exec() == QDialog.Accepted:
            copier = PlanCopier(self.planManager.activePlan)

            # if copying assignments, we don't need a background task, so no need for a progress dialog
            if not dlgCopyPlan.copyAssignments:
                progress = self.startProgress(tr('Creating plan layers...'))
                progress.canceled.connect(copier.cancel)
                copier.progressChanged.connect(progress.setValue)
            else:
                copier.copyComplete.connect(self.triggerUpdate)

            copier.copyComplete.connect(self.appendPlan)
            copier.copyPlan(
                dlgCopyPlan.planName,
                dlgCopyPlan.description,
                dlgCopyPlan.geoPackagePath,
                dlgCopyPlan.copyAssignments
            )

    def importPlan(self):
        if not self.checkActivePlan(tr('import')):
            return

        dlgImportPlan = DlgImportPlan(self.planManager.activePlan, self.iface.mainWindow())
        if dlgImportPlan.exec() == QDialog.Accepted:
            importer = AssignmentImporter(self.iface) \
                .setSourceFile(dlgImportPlan.equivalencyFileName) \
                .setJoinField(dlgImportPlan.joinField) \
                .setHeaderRow(dlgImportPlan.headerRow) \
                .setGeoColumn(dlgImportPlan.geoColumn) \
                .setDistColumn(dlgImportPlan.distColumn) \
                .setDelimiter(dlgImportPlan.delimiter) \
                .setQuoteChar(dlgImportPlan.quotechar)

            progress = self.startProgress(tr('Importing assignments...'))
            importer.progressChanged.connect(progress.setValue)
            progress.canceled.connect(importer.cancel)
            importer.importComplete.connect(self.planManager.activePlan.assignLayer.triggerRepaint)
            if not importer.importPlan(self.planManager.activePlan):
                self.endProgress(progress)

    def importShapefile(self):
        if not self.checkActivePlan(self.tr('import')):
            return

        dlgImportPlan = DlgImportShape(self.planManager.activePlan, self.iface.mainWindow())
        if dlgImportPlan.exec() == QDialog.Accepted:
            importer = ShapefileImporter(self.iface) \
                .setSourceFile(dlgImportPlan.shapefileFileName) \
                .setDistField(dlgImportPlan.distField) \
                .setNameField(dlgImportPlan.nameField) \
                .setMembersField(dlgImportPlan.membersField)

            progress = self.startProgress(self.tr('Importing shapefile...'))
            progress.canceled.connect(importer.cancel)
            importer.progressChanged.connect(progress.setValue)
            importer.importComplete.connect(self.triggerUpdate)
            if not importer.importPlan(self.planManager.activePlan):
                self.endProgress(progress)

    def exportPlan(self):
        def planExported():
            self.iface.messageBar().pushMessage(
                "Success", f"Export of {plan.name} complete!", level=Qgis.Success)

        def exportError():
            for msg, level in export.errors():
                self.iface.messageBar().pushMessage("Error", msg, level=level)

        if not self.checkActivePlan(tr('export')):
            return

        dlgExportPlan = DlgExportPlan(self.planManager.activePlan, self.iface.mainWindow())
        if dlgExportPlan.exec_() == QDialog.Accepted:
            plan = self.planManager.activePlan
            if dlgExportPlan.exportEquivalency or dlgExportPlan.exportShapefile:
                export = PlanExporter(
                    plan,
                    dlgExportPlan.equivalencyFileName if dlgExportPlan.exportEquivalency else None,
                    dlgExportPlan.shapefileFileName if dlgExportPlan.exportShapefile else None,
                    dlgExportPlan.equivalencyGeography,
                    dlgExportPlan.includeUnassigned,
                    dlgExportPlan.includeDemographics,
                    dlgExportPlan.includeMetrics
                )

                progress = self.startProgress(tr('Exporting redistricting plan...'))
                progress.canceled.connect(export.cancel)
                export.progressChanged.connect(progress.setValue)
                export.exportComplete.connect(planExported)
                export.exportTerminated.connect(exportError)
                export.export()

    def selectPlan(self, plan):
        """Make the selected plan the active plan"""
        self.planManager.setActivePlan(plan)
        self.project.setDirty()

    def deletePlan(self, plan: RedistrictingPlan):
        if plan in self.planManager:
            dlg = DlgConfirmDelete(plan, self.iface.mainWindow())
            if dlg.exec() == QDialog.Accepted:
                if dlg.removeLayers():
                    self.layerTreeManager.removeGroup(plan)
                    if dlg.deleteGeoPackage():
                        path = plan.geoPackagePath
                self.planManager.removePlan(plan)
                del plan
                if dlg.removeLayers() and dlg.deleteGeoPackage():
                    d = pathlib.Path(path).parent
                    g = str(pathlib.Path(path).name) + '*'
                    for f in d.glob(g):
                        f.unlink()

                self.project.setDirty()

    def activatePlan(self, checked):
        if checked:
            action: QAction = self.planActions.checkedAction()
            plan = action.data()
            if plan != self.planManager.activePlan:
                self.planManager.setActivePlan(plan)
                self.project.setDirty()

    # helper methods

    def appendPlan(self, plan: RedistrictingPlan):
        self.styler.stylePlan(plan)
        self.layerTreeManager.createGroup(plan)
        self.planManager.appendPlan(plan)

    def buildPlan(self, builder: PlanBuilder, importer: AssignmentImporter):
        def layersCreated(plan: RedistrictingPlan):
            nonlocal progress
            self.appendPlan(plan)
            self.endProgress(progress)

            if importer:
                progress = self.startProgress(tr('Importing assignments...'))
                progress.canceled.connect(importer.cancel)
                importer.progressChanged.connect(progress.setValue)
                importer.importComplete.connect(self.triggerUpdate)
                importer.importTerminated.connect(self.endProgress)
                importer.importPlan(plan)

        def buildError(builder: PlanBuilder):
            if not builder.isCancelled():
                self.endProgress(progress)
                self.pushErrors(builder.errors())

        progress = self.startProgress(tr('Creating plan layers...'))
        progress.canceled.connect(builder.cancel)
        builder.progressChanged.connect(progress.setValue)
        builder.layersCreated.connect(layersCreated)
        builder.builderError.connect(buildError)

        if not builder.createPlan(QgsProject.instance()):
            self.endProgress(progress)
            self.pushErrors(builder.errors())

    def triggerUpdate(self, plan: RedistrictingPlan):
        self.endProgress()
        self.updateService.updateDistricts(plan, needDemographics=True, needGeometry=True, needSplits=True)