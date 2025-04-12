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
from typing import (
    TYPE_CHECKING,
    Iterable,
    Optional
)

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsProject,
    QgsVectorLayer
)
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
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
from ..models import (
    GeoFieldsModel,
    RdsPlan
)
from ..services import (  # ShapefileImporter
    DistrictUpdater,
    LayerTreeManager,
    PlanBuilder,
    PlanCopier,
    PlanEditor,
    PlanExporter,
    PlanImporter,
    PlanImportService,
    PlanListModel,
    PlanManager,
    PlanStylerService
)
from ..services.actions import PlanAction
from ..services.tasks.autoassign import AutoAssignUnassignedUnits
from ..utils import tr
from .base import BaseController

if TYPE_CHECKING:
    from qgis.PyQt.QtCore import QT_VERSION
    if QT_VERSION >= 0x060000:
        from PyQt6.QtGui import (  # type: ignore[import]
            QAction,
            QActionGroup
        )
    else:
        from PyQt5.QtWidgets import (  # type: ignore[import]
            QAction,
            QActionGroup
        )

else:
    from qgis.PyQt.QtGui import (
        QAction,
        QActionGroup
    )


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
        importService: PlanImportService,
        parent: Optional[QObject] = None
    ):
        super().__init__(iface, project, planManager, toolbar, parent)
        self.layerTreeManager = layerTreeManager
        self.styler = planStyler
        self.updateService = updateService
        self.importService = importService

        self.icon = QIcon(':/plugins/redistricting/icon.png')
        self.menuName = tr('&Redistricting')

        self.menu = QMenu(self.menuName)
        self.menu.setIcon(self.icon)

        self.menuButton = QToolButton()
        self.menuButton.setMenu(self.menu)
        self.menuButton.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.menuButton.setIcon(self.icon)
        self.menuButton.setToolTip(tr('Redistricting Utilities'))

        self.toolBtnAction: QAction = None

        self.planMenu: QMenu = None
        self.planActions: QActionGroup = None
        self.vectorSubMenu: QAction = None

        self.planManagerDlg: DlgSelectPlan = None
        self.planModel: PlanListModel = None

        self.createActions()

    def load(self):
        self.planManager.activePlanChanged.connect(self.enableActivePlanActions)
        self.planManager.planAdded.connect(self.planAdded)
        self.planManager.planRemoved.connect(self.planRemoved)
        self.planManager.cleared.connect(self.clearPlanMenu)
        self.project.layersAdded.connect(self.enableNewPlan)
        self.project.layersRemoved.connect(self.enableNewPlan)
        self.updateService.updateComplete.connect(self.planDistrictsUpdated)
        self.importService.importComplete.connect(self.importComplete)

        self.planModel = PlanListModel(self.planManager)

        self.toolBtnAction: QAction = self.toolbar.addWidget(self.menuButton)

        self.planMenu = self.menu.addMenu(self.icon, tr('&Redistricting Plans'))
        self.planActions = QActionGroup(self.iface.mainWindow())

        self.vectorSubMenu: QAction = self.iface.vectorMenu().addMenu(self.menuButton.menu())

    def unload(self):
        if self.planManagerDlg is not None:
            self.planManagerDlg.close()
            self.planManagerDlg.deleteLater()
            self.planManagerDlg = None

        self.planManager.activePlanChanged.disconnect(self.enableActivePlanActions)
        self.planManager.planAdded.disconnect(self.planAdded)
        self.planManager.planRemoved.disconnect(self.planRemoved)
        self.planManager.cleared.disconnect(self.clearPlanMenu)
        self.project.layersAdded.disconnect(self.enableNewPlan)
        self.project.layersRemoved.disconnect(self.enableNewPlan)
        self.updateService.updateComplete.disconnect(self.planDistrictsUpdated)
        self.importService.importComplete.disconnect(self.importComplete)

        self.planModel = None
        self.toolbar.removeAction(self.toolBtnAction)
        self.toolBtnAction = None
        self.iface.vectorMenu().removeAction(self.vectorSubMenu)
        self.vectorSubMenu = None
        self.planActions.setParent(None)
        self.planActions = None
        self.planMenu.setParent(None)
        self.planMenu = None

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
            tr('New Plan'),
            tooltip=tr('Create a new redistricting plan'),
            callback=self.newPlan,
            parent=self.iface.mainWindow()
        )
        self.actionNewPlan.setEnabled(False)
        self.menu.addAction(self.actionNewPlan)

        self.actionEditActivePlan = self.actions.createPlanAction(
            'actionEditActivePlan',
            QIcon(':/plugins/redistricting/editplan.svg'),
            tr('Edit Active Plan'),
            callback=self.editPlan,
            parent=self.iface.mainWindow()
        )
        self.actionEditActivePlan.setEnabled(False)
        self.menu.addAction(self.actionEditActivePlan)

        self.actionCopyPlan = self.actions.createPlanAction(
            'actionCopyPlan',
            QIcon(':/plugins/redistricting/copyplan.svg'),
            tr('Copy Active Plan'),
            tooltip=tr('Copy the active plan to a new redistricting plan'),
            callback=self.copyPlan,
            parent=self.iface.mainWindow()
        )
        self.actionCopyPlan.setEnabled(False)
        self.menu.addAction(self.actionCopyPlan)

        self.actionImportAssignments = self.actions.createPlanAction(
            'actionImportAssignments',
            QIcon(':/plugins/redistricting/importplan.svg'),
            tr('Import Equivalency File'),
            tooltip=tr('Import assignments to active plan from equivalency file'),
            callback=self.importPlan,
            parent=self.iface.mainWindow()
        )
        self.actionImportAssignments.setEnabled(False)
        self.menu.addAction(self.actionImportAssignments)

        self.actionImportShapefile = self.actions.createPlanAction(
            'actionImportShapefile',
            QIcon(':/plugins/redistricting/importplan.svg'),
            tr('Import Shapefile'),
            tooltip=tr('Import assignments to active plan from shapefile'),
            callback=self.importShapefile,
            parent=self.iface.mainWindow()
        )
        self.actionImportShapefile.setEnabled(False)
        self.menu.addAction(self.actionImportShapefile)

        self.actionExportPlan = self.actions.createPlanAction(
            'actionExportPlan',
            QIcon(':/plugins/redistricting/exportplan.svg'),
            tr('Export Active Plan'),
            tooltip=tr('Export plan as equivalency and/or shapefile'),
            callback=self.exportPlan,
            parent=self.iface.mainWindow()
        )
        self.actionExportPlan.setEnabled(False)
        self.menu.addAction(self.actionExportPlan)

        self.actionSelectPlan = self.actions.createPlanAction(
            'actionSelectPlan',
            QIcon(':/plugins/redistricting/selectplan.svg'),
            tr('Select Plan'),
            tooltip=tr('Make the selected plan the active plan'),
            callback=self.selectPlan,
            parent=self.iface.mainWindow()
        )
        self.actionSelectPlan.setEnabled(False)

        self.actionEditPlan = self.actions.createPlanAction(
            'actionEditPlan',
            QIcon(':/plugins/redistricting/icon.png'),
            tr('Edit Plan'),
            callback=self.editPlan,
            parent=self.iface.mainWindow()
        )
        self.actionEditPlan.setEnabled(False)

        self.actionDeletePlan = self.actions.createPlanAction(
            'actionDeletePlan',
            QIcon(':/plugins/redistricting/deleteplan.svg'),
            tr('Delete Plan'),
            tooltip=tr('Remove the selected plan from the project'),
            callback=self.deletePlan,
            parent=self.iface.mainWindow()
        )
        self.actionDeletePlan.setEnabled(False)

        self.actionAutoAssign = self.actions.createAction(
            "actionAutoAssign",
            QgsApplication.getThemeIcon('/algorithms/mAlgorithmVoronoi.svg'),
            tr('Auto-assign Units'),
            tooltip=tr('Attempt to automatically assign unassigned units to districts in the active plan'),
            callback=self.autoassign,
            parent=self.iface.mainWindow()
        )
        self.actionAutoAssign.setEnabled(False)
        self.menu.addAction(self.actionAutoAssign)

    # slots

    def planDistrictsUpdated(self, plan: RdsPlan, districts: Iterable[int]):  # pylint: disable=unused-argument
        self.project.setDirty()

    def enableActivePlanActions(self, plan: Optional[RdsPlan]):
        self.actionEditActivePlan.setEnabled(plan is not None)
        self.actionEditActivePlan.setTarget(plan)
        self.actionCopyPlan.setEnabled(plan is not None and plan.isValid())
        self.actionCopyPlan.setTarget(plan)
        self.actionImportAssignments.setEnabled(plan is not None and plan.isValid())
        self.actionImportAssignments.setTarget(plan)
        self.actionImportShapefile.setEnabled(plan is not None and plan.isValid())
        self.actionImportShapefile.setTarget(plan)
        self.actionExportPlan.setEnabled(
            plan is not None and plan.assignLayer is not None and plan.distLayer is not None
        )
        self.actionExportPlan.setTarget(plan)
        self.actionAutoAssign.setEnabled(
            plan is not None and plan.assignLayer is not None and plan.distField is not None
            and not plan.metrics.complete and len(plan.districts) > 1
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

    def updatePlanManagerActions(self, index: int):
        plan = self.planManager[index]
        self.actionEditPlan.setTarget(plan)
        self.actionSelectPlan.setTarget(plan)
        self.actionSelectPlan.setEnabled(plan != self.activePlan and plan.isValid())
        self.actionDeletePlan.setTarget(plan)

    def clearPlanMenu(self):
        self.planMenu.clear()
        del self.planActions
        self.planActions = QActionGroup(self.iface.mainWindow())
        self.actionNewPlan.setEnabled(
            any(isinstance(layer, QgsVectorLayer)
                for layer in self.project.mapLayers(True).values())
        )
        self.actionSelectPlan.setEnabled(False)

    def addPlanToMenu(self, plan: RdsPlan):
        action = QAction(text=plan.name, parent=self.planActions)
        action.setObjectName(plan.name)
        action.setToolTip(plan.description)
        action.setCheckable(True)
        action.setData(plan)
        action.triggered.connect(self.activatePlan)
        self.planMenu.addAction(action)

    def removePlanFromMenu(self, plan: RdsPlan):
        action: QAction = self.planActions.findChild(QAction, plan.name)
        if action:
            action.triggered.disconnect(self.activatePlan)
            self.planMenu.removeAction(action)
            self.planActions.removeAction(action)

    def planAdded(self, plan: RdsPlan):
        self.addPlanToMenu(plan)
        plan.districtDataChanged.connect(self.project.setDirty)
        self.updateService.watchPlan(plan)
        self.actionSelectPlan.setEnabled(len(self.planManager) > 0)

    def planRemoved(self, plan: RdsPlan):
        self.removePlanFromMenu(plan)
        self.updateService.unwatchPlan(plan)
        self.actionSelectPlan.setEnabled(len(self.planManager) > 0)
        plan.districtDataChanged.disconnect(self.project.setDirty)

    # action slots

    def showPlanManager(self):
        """Display the plan manager window"""
        if self.planManagerDlg is None:
            self.planManagerDlg = DlgSelectPlan(self.iface.mainWindow())
            self.planManagerDlg.setModel(self.planModel)
            self.planManagerDlg.currentIndexChanged.connect(self.updatePlanManagerActions)
            if self.activePlan is not None:
                self.planManagerDlg.setCurrentIndex(self.planManager.index(self.activePlan))

            self.planManagerDlg.setNewAction(self.actionNewPlan)
            self.planManagerDlg.setEditAction(self.actionEditPlan)
            self.planManagerDlg.setSelectAction(self.actionSelectPlan)
            self.planManagerDlg.setDeleteAction(self.actionDeletePlan)

        self.planManagerDlg.show()

    def newPlan(self):
        """Display new redistricting plan dialog and create new plan"""
        if len(self.project.mapLayers()) == 0:
            self.iface.messageBar().pushMessage(
                tr("Oops!"),
                tr("Cannot create a redistricting plan for an "
                   "empty project. Try adding some layers."),
                level=Qgis.MessageLevel.Warning,
                duration=5)
            return

        dlgNewPlan = DlgEditPlan(parent=self.iface.mainWindow())
        if dlgNewPlan.exec() == QDialog.DialogCode.Accepted:
            builder = PlanBuilder() \
                .setName(dlgNewPlan.planName()) \
                .setNumDistricts(dlgNewPlan.numDistricts()) \
                .setNumSeats(dlgNewPlan.numSeats()) \
                .setDescription(dlgNewPlan.description()) \
                .setDeviation(dlgNewPlan.deviation()) \
                .setDeviationType(dlgNewPlan.deviationType()) \
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
                importer = self.importService.importEquivalencyFile(
                    None,
                    dlgNewPlan.importPath(),
                    dlgNewPlan.importField(),
                    dlgNewPlan.importHeaderRow(),
                    dlgNewPlan.importDelim(),
                    dlgNewPlan.importQuote(),
                    dlgNewPlan.importGeoCol(),
                    dlgNewPlan.importDistCol(),
                    startTask=False
                )
            else:
                importer = None

            self.buildPlan(builder, importer)

    def editPlan(self, plan=None):
        """Open redistricting plan in the edit dialog"""
        if not isinstance(plan, RdsPlan):
            plan = self.planManager.activePlan

        if not plan:
            return

        dlgEditPlan = DlgEditPlan(plan, self.iface.mainWindow())
        if dlgEditPlan.exec() == QDialog.DialogCode.Accepted:
            builder = PlanEditor.fromPlan(plan) \
                .setName(dlgEditPlan.planName()) \
                .setNumDistricts(dlgEditPlan.numDistricts()) \
                .setNumSeats(dlgEditPlan.numSeats()) \
                .setDescription(dlgEditPlan.description()) \
                .setDeviation(dlgEditPlan.deviation()) \
                .setDeviationType(dlgEditPlan.deviationType()) \
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

    def copyPlan(self, plan=None):
        if not isinstance(plan, RdsPlan):
            if not self.checkActivePlan(tr('copy')):
                return

        dlgCopyPlan = DlgCopyPlan(self.planManager.activePlan, self.iface.mainWindow())
        if dlgCopyPlan.exec() == QDialog.DialogCode.Accepted:
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

    def importComplete(self, plan):
        if plan != self.activePlan:
            return

        self.activePlan.assignLayer.triggerRepaint()

    def importPlan(self, plan=None):
        if not isinstance(plan, RdsPlan):
            if not self.checkActivePlan(tr('import')):
                return

        dlgImportPlan = DlgImportPlan(self.activePlan, self.iface.mainWindow())
        if dlgImportPlan.exec() == QDialog.Accepted:
            progress = self.startProgress(tr('Importing assignments...'))
            importer = self.importService.importEquivalencyFile(
                self.activePlan,
                dlgImportPlan.equivalencyFileName,
                dlgImportPlan.joinField,
                dlgImportPlan.headerRow,
                dlgImportPlan.geoColumn,
                dlgImportPlan.distColumn,
                dlgImportPlan.delimiter,
                dlgImportPlan.quotechar,
                progress,
            )
            if importer is None or not importer.isValid():
                self.endProgress(progress)

    def importShapefile(self, plan=None):
        if not isinstance(plan, RdsPlan):
            if not self.checkActivePlan(self.tr('import')):
                return

        dlgImportPlan = DlgImportShape(self.iface.mainWindow())
        if dlgImportPlan.exec() == QDialog.DialogCode.Accepted:
            # importer = ShapefileImporter(self.iface) \
            #     .setSourceFile(dlgImportPlan.shapefileFileName) \
            #     .setDistField(dlgImportPlan.distField) \
            #     .setNameField(dlgImportPlan.nameField) \
            #     .setMembersField(dlgImportPlan.membersField)

            progress = self.startProgress(self.tr('Importing shapefile...'))
            importer = self.importService.importShapeFile(
                self.activePlan,
                dlgImportPlan.shapefileFileName,
                dlgImportPlan.distField,
                dlgImportPlan.nameField,
                dlgImportPlan.membersField,
                progress
            )

            # progress.canceled.connect(importer.cancel)
            # importer.progressChanged.connect(progress.setValue)
            # importer.importComplete.connect(self.triggerUpdate)
            # if not importer.importPlan(self.planManager.activePlan):
            if importer is None or not importer.isValid():
                self.endProgress(progress)

    def exportPlan(self, plan=None):
        def planExported():
            self.iface.messageBar().pushMessage(
                "Success", f"Export of {plan.name} complete!", level=Qgis.MessageLevel.Success)

        def exportError():
            for msg, level in export.errors():  # pylint: disable=used-before-assignment
                self.iface.messageBar().pushMessage("Error", msg, level=level)

        if not isinstance(plan, RdsPlan):
            if not self.checkActivePlan(tr('export')):
                return
            plan = self.activePlan

        dlgExportPlan = DlgExportPlan(self.iface.mainWindow())
        dlgExportPlan.cmbGeography.setModel(GeoFieldsModel(plan, self))

        if dlgExportPlan.exec() == QDialog.DialogCode.Accepted:
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

    def selectPlan(self, plan: Optional[RdsPlan] = None):
        """Make the selected plan the active plan"""
        if plan is None:
            action = self.sender()
            if isinstance(action, PlanAction):
                plan = action.target()

        if not isinstance(plan, RdsPlan):
            return

        self.planManager.setActivePlan(plan)
        self.project.setDirty()
        action: QAction = self.planActions.findChild(QAction, plan.name)
        if action is not None:
            action.setChecked(True)

    def deletePlan(self, plan: RdsPlan):
        if plan in self.planManager:
            dlg = DlgConfirmDelete(plan, self.iface.mainWindow())
            if dlg.exec() == QDialog.DialogCode.Accepted:
                if dlg.removeLayers():
                    self.layerTreeManager.removeGroup(plan)
                    if dlg.deleteGeoPackage():
                        path = plan.geoPackagePath
                self.planManager.removePlan(plan)
                del plan
                if dlg.removeLayers() and dlg.deleteGeoPackage():
                    d = pathlib.Path(path).parent  # pylint: disable=used-before-assignment
                    g = str(pathlib.Path(path).name) + '*'
                    for f in d.glob(g):
                        f.unlink()

                self.project.setDirty()

    def activatePlan(self, checked):
        if checked:
            action: QAction = self.planActions.checkedAction()
            plan = action.data()
            if plan != self.planManager.activePlan:
                self.selectPlan(plan)

    # helper methods

    def appendPlan(self, plan: RdsPlan, makeActive=True):
        self.styler.stylePlan(plan)
        self.layerTreeManager.createGroup(plan)
        self.planManager.appendPlan(plan, makeActive)
        self.project.setDirty()

    def buildPlan(self, builder: PlanBuilder, importer: Optional[PlanImporter] = None):
        def layersCreated(plan: RdsPlan):
            nonlocal progress
            self.appendPlan(plan)
            self.endProgress(progress)

            if importer is not None:
                progress = self.startProgress(tr('Importing assignments...'))
                importer.importComplete.connect(self.triggerUpdate)
                importer.importTerminated.connect(self.endProgress)
                self.importService.startImport(plan, importer)
                # importer.importPlan(plan)

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

    def triggerUpdate(self, plan: RdsPlan):
        self.endProgress()
        self.updateService.updateDistricts(plan, needDemographics=True, needGeometry=True)

    def autoassign(self):
        def assignComplete():
            self.iface.messageBar().pushInfo(
                "Success!", f"Auto-assign completed succesfully: {len(task.update)} units were assigned to districts; {len(task.indeterminate)} units could not be assigned."
            )

        def assignError():
            if task.isCanceled():
                return

            self.iface.messageBar().pushWarning(
                "Error assigning units to districts", str(task.exception)
            )

        task = AutoAssignUnassignedUnits(self.activePlan.assignLayer, self.activePlan.distField)
        task.taskCompleted.connect(assignComplete)
        task.taskTerminated.connect(assignError)
        QgsApplication.taskManager().addTask(task)
