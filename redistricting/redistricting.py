# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin

        QGIS plugin for building political districts from geographic units
        (Originally generated using Plugin Builder bygsherman@geoapt.com
        and then heavily modified)

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
import pathlib
from typing import List
from uuid import UUID
from qgis.core import Qgis, QgsApplication, QgsProject, QgsField, QgsVectorLayer, QgsReadWriteContext
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import Qt, QCoreApplication, QTranslator, QSettings
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QDialog, QAction, QToolBar, QMenu, QToolButton, QProgressDialog
from qgis.PyQt.QtXml import QDomDocument

from .resources import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .gui import (
    DlgConfirmDelete,
    DlgCopyPlan,
    DlgEditPlan,
    DlgExportPlan,
    DlgImportPlan,
    DlgImportShape,
    DlgNewDistrict,
    DlgSelectPlan,
    DockRedistrictingToolbox,
    DockDistrictDataTable,
    DockPendingChanges,
    PaintDistrictsTool,
    PaintMode
)
from .core import (
    ProjectStorage,
    RedistrictingPlan,
    PlanBuilder,
    PlanEditor,
    PlanStyler,
    PlanExporter,
    AssignmentImporter,
    ShapefileImporter,
    PlanCopier
)


class Redistricting:
    """QGIS Redistricting Plugin"""

    def __init__(self, iface: QgisInterface):
        self.name = self.__class__.__name__
        self.iface = iface
        self.canvas = self.iface.mapCanvas()

        self.project = QgsProject.instance()
        self.projectClosing = False
        self.projectSignalsConnected = False

        self.importer = None

        self.redistrictingPlans: List[RedistrictingPlan] = []
        self.activePlan: RedistrictingPlan = None

        self.distSource = None
        self.distTarget = None
        self.paintGeoField: QgsField = None

        self.dockwidget: DockRedistrictingToolbox = None
        self.dataTableWidget: DockDistrictDataTable = None
        self.pendingChangesWidget: DockPendingChanges = None
        self.mapTool: PaintDistrictsTool = None

        # initialize plugin directory
        self.pluginDir = pathlib.Path(__file__).parent

        if not hasattr(Qgis, 'UserCanceled'):
            Qgis.UserCanceled = Qgis.Success + 0x100

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        localePath = self.pluginDir / 'i18n' / f'{self.name}_{locale}.qm'

        if localePath.exists():
            self.translator = QTranslator()
            self.translator.load(str(localePath))
            QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menuName = self.tr('&Redistricting')
        self.icon = QIcon(':/plugins/redistricting/icon.png')

        self.menu = None
        self.toolbar = None
        self.menuButton = None
        self.toolBtnAction = None

        self.dlg = None

    @staticmethod
    def tr(message):
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('redistricting', message)

    def addAction(
            self,
            iconPath,
            text,
            callback,
            enabledFlag=True,
            addToMenu=False,
            addToToolbar=False,
            addToToolbarMenu=False,
            statusTip=None,
            parent=None) -> QAction:

        if isinstance(iconPath, QIcon):
            icon = iconPath
        else:
            icon = QIcon(iconPath)

        if isinstance(callback, QAction):
            action = callback
            action.setIcon(icon)
            action.setParent(parent)
            action.setText(text)
            action.setEnabled(enabledFlag)
        else:
            action = QAction(icon, text, parent)
            action.triggered.connect(callback)
            action.setEnabled(enabledFlag)

        if statusTip is not None:
            action.setStatusTip(statusTip)

        if addToToolbar:
            self.toolbar.addAction(action)

        if addToMenu:
            self.iface.addPluginToVectorMenu(
                self.menuName,
                action)

        if addToToolbarMenu:
            self.menu.addAction(action)

        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries, toolbar buttons, actions, and dock widgets."""
        if not self.projectSignalsConnected:
            self.project.readProjectWithContext.connect(self.onReadProject)
            self.project.writeProject.connect(self.onWriteProject)
            # there is no signal that gets triggered before a project
            # is closed, but removeAll comes close
            self.project.removeAll.connect(self.onProjectClosing)

            # layersWillBeRemoved signal is triggered when a project is
            # closed or when the user removes a layer, and there seems
            # to be no way to disinguish. We use a flag set in the
            # signal handler for the project cleared signal (the closest
            # thing to a 'project closed' signal QGIS seems to have) to
            # ignore this signal when triggered in the context of a
            # project closing
            self.project.layersWillBeRemoved.connect(self.onLayersWillBeRemoved)

            self.project.layersAdded.connect(self.updateNewPlanAction)
            self.project.layersRemoved.connect(self.updateNewPlanAction)

            self.projectSignalsConnected = True

        self.menu = QMenu(self.menuName, self.iface.mainWindow())
        self.menu.setIcon(self.icon)

        self.toolbar: QToolBar = self.iface.addToolBar(self.name)
        self.toolbar.setObjectName(self.name)

        self.menuButton = QToolButton(self.iface.mainWindow())
        self.menuButton.setMenu(self.menu)
        self.menuButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.menuButton.setIcon(self.icon)
        self.menuButton.setToolTip(self.tr('Redistricting Utilities'))

        self.toolBtnAction = self.toolbar.addWidget(self.menuButton)
        m: QMenu = self.iface.vectorMenu().addMenu(self.menuName)
        m.addMenu(self.menuButton.menu())

        # pylint: disable=attribute-defined-outside-init
        self.actionShowPlanManager = self.addAction(
            ':/plugins/redistricting/planmanager.svg',
            self.tr('Plan Manager'),
            addToToolbarMenu=True,
            callback=self.showPlanManager,
            parent=self.iface.mainWindow()
        )
        self.menuButton.clicked.connect(
            lambda: self.actionShowPlanManager.trigger()  # pylint: disable=unnecessary-lambda
        )

        self.actionNewPlan = self.addAction(
            ':/plugins/redistricting/addplan.svg',
            text=self.tr('New Redistricting Plan'),
            statusTip=self.tr('Create a new redistricting plan'),
            addToToolbarMenu=True,
            enabledFlag=False,
            callback=self.newPlan,
            parent=self.iface.mainWindow()
        )

        self.actionCopyPlan = self.addAction(
            ':/plugins/redistricting/copyplan.svg',
            text=self.tr('Copy Plan'),
            statusTip=self.tr(
                'Copy the active plan to a new redistricting plan'),
            addToToolbarMenu=True,
            enabledFlag=False,
            callback=self.copyPlan,
            parent=self.iface.mainWindow()
        )

        self.actionEditPlan = self.addAction(
            ':/plugins/redistricting/icon.png',
            self.tr('Edit Plan'),
            callback=self.editPlan,
            parent=self.iface.mainWindow()
        )

        self.actionImportAssignments = self.addAction(
            ':/plugins/redistricting/importplan.svg',
            text=self.tr('Import Equivalency File'),
            statusTip=self.tr('Import equivalency file to district field'),
            addToToolbarMenu=True,
            enabledFlag=False,
            callback=self.importPlan,
            parent=self.iface.mainWindow()
        )

        self.actionImportShapefile = self.addAction(
            ':/plugins/redistricting/importplan.svg',
            text=self.tr('Import Shapefile'),
            statusTip=self.tr('Import assignments from sahpefile'),
            addToToolbarMenu=True,
            enabledFlag=False,
            callback=self.importShapefile,
            parent=self.iface.mainWindow()
        )

        self.actionExportPlan = self.addAction(
            ':/plugins/redistricting/exportplan.svg',
            text=self.tr('Export Plan'),
            statusTip=self.tr('Export plan as equivalency and/or shapefile'),
            addToToolbarMenu=True,
            enabledFlag=False,
            callback=self.exportPlan,
            parent=self.iface.mainWindow()
        )

        self.actionStartPaintDistricts = self.addAction(
            ':/plugins/redistricting/paintpalette.svg',
            self.tr('Paint districts'),
            callback=self.startPaintDistricts,
            enabledFlag=False,
            parent=self.iface.mainWindow()
        )

        self.actionPaintRectangle = self.addAction(
            ':/plugins/redistricting/paintrubberband.svg',
            self.tr('Paint districts within selection rectangle'),
            callback=self.startPaintRectangle,
            enabledFlag=False,
            parent=self.iface.mainWindow()
        )

        self.actionSelectByGeography = self.addAction(
            QgsApplication.getThemeIcon('/mActionSelectFreehand.svg'),
            text=self.tr('Select by geography units'),
            callback=self.selectByGeography,
            enabledFlag=False,
            parent=self.iface.mainWindow()
        )

        self.actionCommitPlanChanges = self.addAction(
            QgsApplication.getThemeIcon('/mActionSaveAllEdits.svg'),
            text=self.tr('Commit changes'),
            statusTip=self.tr(
                'Save all districting changes to the underlying layer'),
            callback=self.onCommitChanges,
            enabledFlag=False,
            parent=self.iface.mainWindow()
        )

        self.actionRollbackPlanChanges = self.addAction(
            QgsApplication.getThemeIcon('/mActionCancelEdits.svg'),
            text=self.tr('Rollback changes'),
            statusTip=self.tr(
                'Discard all unsaved districting changes'),
            callback=self.onRollbackChanges,
            enabledFlag=False,
            parent=self.iface.mainWindow()
        )
        # pylint: enable=attribute-defined-outside-init

        self.mapTool = PaintDistrictsTool(self.canvas)

        if not self.dockwidget:
            self.dockwidget = self.setupToolboxDockWidget()
        if not self.dataTableWidget:
            self.dataTableWidget = self.setupDataTableDockWidget()
        if not self.pendingChangesWidget:
            self.pendingChangesWidget = self.setupPendingChangesWidget()

        self.setActivePlan(self.activePlan)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        if self.projectSignalsConnected:
            self.project.readProjectWithContext.disconnect(self.onReadProject)
            self.project.writeProject.disconnect(self.onWriteProject)
            self.project.removeAll.disconnect(self.onProjectClosing)
            self.project.layersWillBeRemoved.disconnect(self.onLayersWillBeRemoved)
            self.project.layersAdded.disconnect(self.updateNewPlanAction)
            self.project.layersRemoved.disconnect(self.updateNewPlanAction)
            self.projectSignalsConnected = False

        self.iface.removeDockWidget(self.dockwidget)
        self.dockwidget.destroy()
        self.dockwidget = None
        self.iface.removeDockWidget(self.dataTableWidget)
        self.dataTableWidget.destroy()
        self.dataTableWidget = None
        self.iface.removeDockWidget(self.pendingChangesWidget)
        self.pendingChangesWidget.destroy()
        self.pendingChangesWidget = None
        self.mapTool = None

        for action in self.actions:
            self.iface.removePluginVectorMenu(self.menuName, action)
            self.iface.removeToolBarIcon(action)

        self.iface.removePluginVectorMenu(self.menuName, self.toolBtnAction)

        # remove the toolbar
        del self.toolbar

    def setupToolboxDockWidget(self):
        """Create the dockwidget with tools for painting districts."""
        dockwidget = DockRedistrictingToolbox(self.activePlan)

        dockwidget.geoFieldChanged.connect(self.mapTool.setGeoField)
        dockwidget.sourceChanged.connect(self.mapTool.setSourceDistrict)
        dockwidget.targetChanged.connect(self.setDistTarget)
        dockwidget.btnAssign.setDefaultAction(self.actionStartPaintDistricts)
        dockwidget.btnPaintRectangle.setDefaultAction(self.actionPaintRectangle)
        dockwidget.btnSelectByGeography.setDefaultAction(self.actionSelectByGeography)
        dockwidget.btnCommitUpdate.setDefaultAction(self.actionCommitPlanChanges)
        dockwidget.btnRollbackUpdate.setDefaultAction(self.actionRollbackPlanChanges)
        dockwidget.btnEditPlan.setDefaultAction(self.actionEditPlan)

        self.iface.addDockWidget(Qt.RightDockWidgetArea, dockwidget)

        self.addAction(
            ':/plugins/redistricting/paintdistricts.svg',
            text=self.tr('Paint Districts'),
            statusTip=self.tr(
                'Show/hide tools for creating/editing districts'),
            addToToolbar=True,
            addToMenu=True,
            callback=dockwidget.toggleViewAction(),
            parent=self.iface.mainWindow())

        dockwidget.hide()
        return dockwidget

    def setupDataTableDockWidget(self):
        """Create the dockwidget that displays district statistics."""
        dockwidget = DockDistrictDataTable(self.activePlan)
        self.iface.addDockWidget(
            Qt.BottomDockWidgetArea, dockwidget)

        self.addAction(
            QgsApplication.getThemeIcon('/mActionOpenTable.svg'),
            text=self.tr('District Data'),
            statusTip=self.tr(
                'Show/hide district demographic data/metrics table'),
            addToToolbar=True,
            addToMenu=True,
            callback=dockwidget.toggleViewAction(),
            parent=self.iface.mainWindow())

        dockwidget.hide()
        return dockwidget

    def setupPendingChangesWidget(self):
        """Create the dockwidget with displays the impact of pending
        changes on affected districts."""
        dockwidget = DockPendingChanges(self.activePlan)
        self.iface.addDockWidget(Qt.LeftDockWidgetArea, dockwidget)

        self.addAction(
            ':/plugins/redistricting/preview.svg',
            text=self.tr('Pending Changes'),
            statusTip=self.tr('Show/hide pending changes dock widget'),
            addToToolbar=True,
            addToMenu=True,
            callback=dockwidget.toggleViewAction(),
            parent=self.iface.mainWindow())

        dockwidget.hide()
        return dockwidget

    # --------------------------------------------------------------------------

    def progressCanceled(self):
        """Hide progress dialog and display message on cancel"""
        if self.activePlan and self.activePlan.error():
            error, _ = self.activePlan.error()
        else:
            error = ''

        if error:
            self.iface.messageBar().pushMessage(
                self.tr("Canceled"), error, level=Qgis.Warning)
        else:
            self.iface.messageBar().pushMessage(
                self.tr("Canceled"), f'{self.dlg.labelText()} canceled', level=Qgis.Warning)

    def startProgress(self, text=None, maximum=100, canCancel=True):
        """Create and initialize a progress dialog"""
        if self.dlg:
            try:
                self.dlg.canceled.disconnect(self.progressCanceled)
            except:  # pylint: disable=bare-except
                ...
            self.dlg.close()
        self.dlg = QProgressDialog(
            text, self.tr('Cancel'),
            0, maximum,
            self.iface.mainWindow(),
            Qt.WindowStaysOnTopHint)
        self.dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        if not canCancel:
            self.dlg.setCancelButton(None)
        else:
            self.dlg.canceled.connect(self.progressCanceled)

        return self.dlg

    def endProgress(self, progress: QProgressDialog = None):
        if progress is None:
            progress = self.dlg

        if progress is not None and not progress.wasCanceled():
            progress.canceled.disconnect(self.progressCanceled)
            progress.cancel()
            progress.hide()

    # --------------------------------------------------------------------------

    def onReadProject(self, doc: QDomDocument, context: QgsReadWriteContext):
        self.clear()
        storage = ProjectStorage(self.project, doc, context)
        self.redistrictingPlans.extend(storage.readRedistrictingPlans())
        for plan in self.redistrictingPlans:
            for err, level in plan.errors():
                self.iface.messageBar().pushMessage(err, level)
            plan.planChanged.connect(self.planChanged)

        if len(self.redistrictingPlans) == 1:
            self.setActivePlan(self.redistrictingPlans[0])
        else:
            uuid = storage.readActivePlan()
            if uuid:
                self.setActivePlan(uuid)

    def onWriteProject(self, doc: QDomDocument):
        if len(self.redistrictingPlans) == 0:
            return

        storage = ProjectStorage(self.project, doc)
        storage.writeRedistrictingPlans(self.redistrictingPlans)
        storage.writeActivePlan(self.activePlan)

    def onProjectClosing(self):
        self.projectClosing = True
        self.clear()
        self.dockwidget.hide()
        self.dataTableWidget.hide()

    def onLayersWillBeRemoved(self, layerIds):
        if self.projectClosing:
            self.projectClosing = False
        else:
            deletePlans = set()
            for layer in layerIds:
                for plan in self.redistrictingPlans:
                    if plan.popLayer.id() == layer:
                        deletePlans.add(plan)
                    elif plan.assignLayer.id() == layer:
                        deletePlans.add(plan)
                    elif plan.distLayer.id() == layer:
                        deletePlans.add(plan)
                    elif plan.sourceLayer.id() == layer:
                        plan.sourceLayer = None

            for plan in deletePlans:
                self.removePlan(plan)

    def updateNewPlanAction(self, layers):  # pylint: disable=unused-argument
        self.actionNewPlan.setEnabled(
            any(isinstance(layer, QgsVectorLayer)
                for layer in self.project.mapLayers(True).values())
        )

    # --------------------------------------------------------------------------

    def setDistTarget(self, target):
        if target is None:
            target = self.createDistrict()
        self.mapTool.setTargetDistrict(target)
        if target is None:
            self.canvas.unsetMapTool(self.mapTool)

    def activateMapTool(self, mode):
        self.mapTool.paintMode = mode
        if self.mapTool.targetDistrict is None:
            target = self.createDistrict()
            self.mapTool.setTargetDistrict(target)
        if self.mapTool.canActivate():
            self.activePlan.updateDistricts()
            self.canvas.setMapTool(self.mapTool)

    def startPaintDistricts(self):
        if self.activePlan:
            self.activateMapTool(PaintMode.PaintByGeography)

    def startPaintRectangle(self):
        if self.activePlan:
            self.activateMapTool(PaintMode.PaintRectangle)

    def selectByGeography(self):
        if self.activePlan:
            self.activateMapTool(PaintMode.SelectByGeography)

    def onCommitChanges(self):
        self.activePlan.assignLayer.commitChanges(True)
        self.activePlan.assignLayer.triggerRepaint()

    def onRollbackChanges(self):
        self.activePlan.assignLayer.rollBack(True)
        self.activePlan.assignLayer.triggerRepaint()

    def showPlanManager(self):
        """Display the plan manager window"""
        dlg = DlgSelectPlan(self.redistrictingPlans, self.activePlan)
        dlg.newPlan.connect(self.newPlan)
        dlg.planSelected.connect(self.onPlanSelected)
        dlg.planEdited.connect(self.editPlan)
        dlg.planDeleted.connect(self.deletePlan)
        dlg.exec_()

    def onPlanSelected(self, plan):
        """Make the selected plan the active plan"""
        self.setActivePlan(plan)
        self.project.setDirty()

    def editPlan(self, plan=None):
        """Open redistricting plan in the edit dialog"""
        if not isinstance(plan, RedistrictingPlan):
            plan = self.activePlan
        if not plan:
            return

        dlgEditPlan = DlgEditPlan(plan, None)
        if dlgEditPlan.exec_() == QDialog.Accepted:
            builder = PlanEditor.fromPlan(plan) \
                .setName(dlgEditPlan.planName()) \
                .setNumDistricts(dlgEditPlan.numDistricts()) \
                .setNumSeats(dlgEditPlan.numSeats()) \
                .setDescription(dlgEditPlan.description()) \
                .setDeviation(dlgEditPlan.deviation()) \
                .setGeoIdField(dlgEditPlan.geoIdField()) \
                .setGeoDisplay(dlgEditPlan.geoIdDisplay()) \
                .setSourceLayer(dlgEditPlan.sourceLayer()) \
                .setPopLayer(dlgEditPlan.popLayer()) \
                .setJoinField(dlgEditPlan.joinField()) \
                .setPopField(dlgEditPlan.popField()) \
                .setVAPField(dlgEditPlan.vapField()) \
                .setCVAPField(dlgEditPlan.cvapField()) \
                .setDataFields(dlgEditPlan.dataFields()) \
                .setGeoFields(dlgEditPlan.geoFields())

            if builder.updatePlan():
                self.project.setDirty()

    def deletePlan(self, plan: RedistrictingPlan):
        if plan in self.redistrictingPlans:
            dlg = DlgConfirmDelete(plan)
            if dlg.exec_() == QDialog.Accepted:
                self.removePlan(plan, dlg.removeLayers(), dlg.deleteGeoPackage())

    def layersCreated(self, plan: RedistrictingPlan):
        PlanStyler.style(plan, self.activePlan)
        self.iface.layerTreeView().refreshLayerSymbology(plan.distLayer.id())
        self.iface.layerTreeView().refreshLayerSymbology(plan.assignLayer.id())

        self.appendPlan(plan)

    def newPlan(self):
        """Display new redistricting plan dialog and create new plan"""

        def updateProgress(value: int):
            progress.setValue(value)

        def importStarted():
            # not sure why pylint thinks this variable is used before assignement -- disable
            self.endProgress(progress)  # pylint: disable=used-before-assignment
            progress = self.startProgress(self.tr('Importing assignments...'))
            importer.progressChanged.connect(progress.setValue)
            progress.canceled.connect(importer.cancel)
            self.layersCreated(plan)

        if len(self.project.mapLayers()) == 0:
            self.iface.messageBar().pushMessage(
                self.tr("Oops!"),
                self.tr("Cannot create a redistricting plan for an "
                        "empty project. Try adding some layers."),
                level=Qgis.Warning)
            return

        if self.project.isDirty():
            # the project must be saved before a plan can be created
            self.iface.messageBar().pushMessage(
                self.tr("Wait!"),
                self.tr("Please save your project before "
                        "creating a redistricting plan."),
                level=Qgis.Warning
            )
            return

        dlgNewPlan = DlgEditPlan()
        if dlgNewPlan.exec_() == QDialog.Accepted:
            builder = PlanBuilder() \
                .setName(dlgNewPlan.planName()) \
                .setNumDistricts(dlgNewPlan.numDistricts()) \
                .setNumSeats(dlgNewPlan.numSeats()) \
                .setDescription(dlgNewPlan.description()) \
                .setDeviation(dlgNewPlan.deviation()) \
                .setGeoIdField(dlgNewPlan.geoIdField()) \
                .setGeoDisplay(dlgNewPlan.geoIdDisplay()) \
                .setSourceLayer(dlgNewPlan.sourceLayer()) \
                .setPopLayer(dlgNewPlan.popLayer()) \
                .setJoinField(dlgNewPlan.joinField()) \
                .setPopField(dlgNewPlan.popField()) \
                .setVAPField(dlgNewPlan.vapField()) \
                .setCVAPField(dlgNewPlan.cvapField()) \
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
                builder.setPlanImporter(importer)
            else:
                importer = None

            progress = self.startProgress(self.tr('Creating plan layers...'))
            builder.progressChanged.connect(updateProgress)
            progress.canceled.connect(builder.cancel)

            if importer:
                builder.layersCreated.connect(importStarted)
            else:
                builder.layersCreated.connect(self.layersCreated)

            if not (plan := builder.createPlan(QgsProject.instance())):
                self.endProgress(progress)
                for msg, level in builder.errors():
                    self.iface.messageBar().pushMessage(msg, level)

    def copyPlan(self):
        if not self.checkActivePlan(self.tr('copy')):
            return

        dlgCopyPlan = DlgCopyPlan(self.activePlan)
        if dlgCopyPlan.exec_() == QDialog.Accepted:
            copier = PlanCopier(self.activePlan)
            copier.copyComplete.connect(self.appendPlan)
            copier.copyPlan(dlgCopyPlan.planName, dlgCopyPlan.geoPackagePath, dlgCopyPlan.copyAssignments)

    def importPlan(self):
        if not self.checkActivePlan(self.tr('import')):
            return

        dlgImportPlan = DlgImportPlan(self.activePlan)
        if dlgImportPlan.exec_() == QDialog.Accepted:
            importer = AssignmentImporter(self.iface) \
                .setSourceFile(dlgImportPlan.equivalencyFileName) \
                .setJoinField(dlgImportPlan.joinField) \
                .setHeaderRow(dlgImportPlan.headerRow) \
                .setGeoColumn(dlgImportPlan.geoColumn) \
                .setDistColumn(dlgImportPlan.distColumn) \
                .setDelimiter(dlgImportPlan.delimiter) \
                .setQuoteChar(dlgImportPlan.quotechar)

            progress = self.startProgress(self.tr('Importing assignments...'))
            importer.progressChanged.connect(progress.setValue)
            progress.canceled.connect(importer.cancel)
            importer.importComplete.connect(self.activePlan.assignLayer.triggerRepaint)
            if not importer.importPlan(self.activePlan):
                self.endProgress(progress)

    def importShapefile(self):
        if not self.checkActivePlan(self.tr('import')):
            return

        dlgImportPlan = DlgImportShape(self.activePlan)
        if dlgImportPlan.exec_() == QDialog.Accepted:
            importer = ShapefileImporter(self.iface) \
                .setSourceFile(dlgImportPlan.shapefileFileName) \
                .setDistField(dlgImportPlan.distField) \
                .setNameField(dlgImportPlan.nameField) \
                .setMembersField(dlgImportPlan.membersField)

            progress = self.startProgress(self.tr('Importing shapefile...'))
            importer.progressChanged.connect(progress.setValue)
            progress.canceled.connect(importer.cancel)
            importer.importComplete.connect(self.activePlan.assignLayer.triggerRepaint)
            if not importer.importPlan(self.activePlan):
                self.endProgress(progress)

    def exportPlan(self):
        def planExported():
            self.iface.messageBar().pushMessage(
                "Success", f"Export of {plan.name} complete!", level=Qgis.Success)

        if not self.checkActivePlan(self.tr('export')):
            return

        dlgExportPlan = DlgExportPlan(self.activePlan)
        if dlgExportPlan.exec_() == QDialog.Accepted:
            plan = self.activePlan
            if dlgExportPlan.exportEquivalency or dlgExportPlan.exportShapefile:
                export = PlanExporter(plan,
                                      dlgExportPlan.equivalencyFileName if dlgExportPlan.exportEquivalency else None,
                                      dlgExportPlan.shapefileFileName if dlgExportPlan.exportShapefile else None,
                                      dlgExportPlan.equivalencyGeography,
                                      dlgExportPlan.includeUnassigned,
                                      dlgExportPlan.includeDemographics,
                                      dlgExportPlan.includeMetrics)

                export.exportComplete.connect(planExported)
                export.export(self.startProgress(self.tr('Exporting redistricting plan...')))

    def editingStarted(self):
        self.actionCommitPlanChanges.setEnabled(True)
        self.actionRollbackPlanChanges.setEnabled(True)

    def editingStopped(self):
        self.actionCommitPlanChanges.setEnabled(False)
        self.actionRollbackPlanChanges.setEnabled(False)

    def planChanged(self, plan, prop, newValue, oldValue):  # pylint: disable=unused-argument
        self.project.setDirty()
        if prop in ['total-population', 'deviation', 'pop-field', 'vap-field', 'cvap-field', 'data-fields']:
            self.dataTableWidget.tblDataTable.update()

    def createDistrict(self):
        if not self.checkActivePlan('create district'):
            return None

        if self.activePlan.allocatedDistricts == self.activePlan.numDistricts:
            self.iface.messageBar().pushMessage(
                self.tr("Warning"), self.tr('All districts have already been allocated'), Qgis.Warning)
            self.distTarget = None
            return None

        dlg = DlgNewDistrict(self.activePlan, self.iface.mainWindow())
        if dlg.exec_() == QDialog.Rejected:
            return None

        dist = self.activePlan.addDistrict(
            dlg.districtNumber, dlg.districtName, dlg.members, dlg.description)
        self.dockwidget.setTargetDistrict(dist)
        return dist.district

    # --------------------------------------------------------------------------

    def appendPlan(self, plan: RedistrictingPlan):
        self.redistrictingPlans.append(plan)
        plan.planChanged.connect(self.planChanged)
        self.project.setDirty()
        self.setActivePlan(plan)

    def removePlan(self, plan: RedistrictingPlan, removeLayers=True, deleteGpkg=False):
        if plan in self.redistrictingPlans:
            if plan == self.activePlan:
                self.setActivePlan(None)
            self.redistrictingPlans.remove(plan)

            if removeLayers:
                plan.removeGroup()
                if deleteGpkg:
                    path = plan.geoPackagePath
            del plan
            if removeLayers and deleteGpkg:
                d = pathlib.Path(path).parent
                g = str(pathlib.Path(path).name) + '*'
                for f in d.glob(g):
                    f.unlink()

            self.project.setDirty()

    def clear(self):
        self.setActivePlan(None)
        self.redistrictingPlans.clear()
        if not self.projectClosing:
            self.actionNewPlan.setEnabled(
                any(isinstance(layer, QgsVectorLayer)
                    for layer in self.project.mapLayers(True).values())
            )

    def checkActivePlan(self, action):
        if self.activePlan is None:
            self.iface.messageBar().pushMessage(
                self.tr("Oops!"),
                self.tr(f"Cannot {action}: no active redistricting plan. Try creating a new plan."),
                level=Qgis.Warning
            )
            return False

        return True

    def setActivePlan(self, plan):
        if isinstance(plan, UUID):
            for p in self.redistrictingPlans:
                if p.id == plan:
                    plan = p
                    break
            else:
                return

        if plan is not None and not plan.isValid():
            return

        if self.activePlan != plan or self.activePlan is None:
            if self.activePlan:
                self.activePlan.assignLayer.editingStopped.disconnect(
                    self.editingStopped)
                self.activePlan.assignLayer.editingStarted.disconnect(
                    self.editingStarted)

            self.activePlan = plan

            self.mapTool.plan = self.activePlan
            self.dockwidget.plan = self.activePlan
            self.dataTableWidget.plan = self.activePlan
            self.pendingChangesWidget.plan = self.activePlan

            if self.activePlan and self.activePlan.assignLayer:
                self.activePlan.assignLayer.editingStarted.connect(
                    self.editingStarted)
                self.activePlan.assignLayer.editingStopped.connect(
                    self.editingStopped)

                self.actionCommitPlanChanges.setEnabled(
                    self.activePlan.assignLayer and self.activePlan.assignLayer.isEditable())
                self.actionRollbackPlanChanges.setEnabled(
                    self.activePlan.assignLayer and self.activePlan.assignLayer.isEditable())

            self.actionStartPaintDistricts.setEnabled(
                self.activePlan is not None)
            self.actionPaintRectangle.setEnabled(
                self.activePlan is not None)
            self.actionSelectByGeography.setEnabled(
                self.activePlan is not None)
            self.actionEditPlan.setEnabled(self.activePlan is not None)
            self.actionImportAssignments.setEnabled(
                self.activePlan is not None)
            self.actionImportShapefile.setEnabled(
                self.activePlan is not None)
            self.actionExportPlan.setEnabled(self.activePlan is not None)
            self.actionCopyPlan.setEnabled(self.activePlan is not None)
