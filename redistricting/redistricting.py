# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin

    QGIS plugin for building political districts from geographic units
        (Originally generated using Plugin Builder by
        gsherman@geoapt.com and then heavily modified)

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
from typing import List
from glob import glob
from uuid import UUID
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsProject,
    QgsFeature,
    QgsField,
    QgsReadWriteContext,
    QgsMessageLog,
    QgsVectorLayer,
    QgsFeedback
)
from qgis.gui import QgisInterface, QgsMapTool, QgsMapToolIdentifyFeature
from qgis.PyQt.QtCore import Qt, QCoreApplication, QTranslator, QSettings
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QDialog, QAction, QToolBar, QMenu, QToolButton, QProgressDialog
from qgis.PyQt.QtXml import QDomDocument

from .resources import *
from .gui import *
from .core import (
    ProjectStorage,
    RedistrictingPlan,
    PlanAssignmentEditor,
    PlanStyler,
    PlanExporter,
    PlanImporter,
    PlanCopier
)


class Redistricting:
    def __init__(self, iface: QgisInterface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """

        # Declare instance attributes
        self.iface = iface
        self.canvas = self.iface.mapCanvas()

        self.project = QgsProject.instance()
        self.projectClosing = False
        self.projectSignalsConnected = False

        self.redistrictingPlans: List[RedistrictingPlan] = []
        self.activePlan: RedistrictingPlan = None
        self.distSource = None
        self.distTarget = None
        self.geoSelectField: QgsField = None
        self.dockwidget: DockRedistrictingToolbox = None
        self.dataTableWidget: DockDistrictDataTable = None
        self.pendingChangesWidget: DockPendingChanges = None
        self.mapTool: QgsMapTool = None

        self.name = self.__class__.__name__

        # initialize plugin directory
        self.pluginDir = os.path.dirname(__file__)

        if not hasattr(Qgis, 'UserCanceled'):
            Qgis.UserCanceled = Qgis.Success + 1

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        localePath = os.path.join(
            self.pluginDir,
            'i18n',
            '{}_{}.qm'.format(self.name, locale))

        if os.path.exists(localePath):
            self.translator = QTranslator()
            self.translator.load(localePath)
            QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menuName = self.tr(u'&Redistricting')
        self.icon = QIcon(':/plugins/redistricting/icon.png')
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

        self.dlg = None
        self.assignmentEditor = None

    @staticmethod
    def tr(message):
        """Get the translation for a string using Qt translation API.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
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
            whatsThis=None,
            parent=None) -> QAction:
        """Add a toolbar icon to the toolbar.

        :param iconPath: Path to the icon for this action or an instance of QIcon.
            Can be a resource path (e.g. ':/plugins/foo/bar.png') or a normal file
            system path.
        :type iconPath: str | QIcon

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered or a QAction instance.
        :type callback: function | QAction

        :param enabledFlag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabledFlag: bool

        :param addToMenu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type addToMenu: bool

        :param addToToolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type addToToolbar: bool

        :param statusTip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type statusTip: str

        :param whatsThis: Optional text to show in the status bar when the
            mouse pointer hovers over the action.
        :type whatsThis: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

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

        if whatsThis is not None:
            action.setWhatsThis(whatsThis)

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
            self.project.layersAdded.connect(self.onLayersAdded)
            self.project.layersRemoved.connect(self.onLayersRemoved)
            # layersWillBeRemoved signal is triggered when a project is closed or when
            # the user removes a layer, and there seems to be no way to disinguish. We
            # use a flag set in the signal handler for removeAll (the closest thing to
            # a 'project closed' signal QGIS seems to have) to ignore this signal when
            # triggered in the context of a project closing
            self.project.layersWillBeRemoved.connect(self.onLayersWillBeRemoved)
            # QGIS inexplicably has no signal for when a project is closed, but removeAll
            # seems to come close
            self.project.removeAll.connect(self.onCloseProject)
            self.projectSignalsConnected = True

        self.actionShowPlanManager = self.addAction(
            ':/plugins/redistricting/planmanager.svg',
            self.tr(u'Plan Manager'),
            addToToolbarMenu=True,
            callback=self.showPlanManager,
            parent=self.iface.mainWindow()
        )
        self.menuButton.clicked.connect(
            lambda: self.actionShowPlanManager.trigger())

        self.actionNewPlan = self.addAction(
            ':/plugins/redistricting/addplan.svg',
            text=self.tr(u'New Redistricting Plan'),
            statusTip=self.tr(u'Create a new redistricting plan'),
            addToToolbarMenu=True,
            enabledFlag=False,
            callback=self.newPlan,
            parent=self.iface.mainWindow()
        )

        self.actionCopyPlan = self.addAction(
            ':/plugins/redistricting/copyplan.svg',
            text=self.tr(u'Copy Plan'),
            statusTip=self.tr(
                u'Copy the active plan to a new redistricting plan'),
            addToToolbarMenu=True,
            enabledFlag=False,
            callback=self.copyPlan,
            parent=self.iface.mainWindow()
        )

        self.actionEditPlan = self.addAction(
            ':/plugins/redistricting/icon.png',
            self.tr(u'Edit Plan'),
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
            ':/plugins/redistricting/paintdistricts.svg',
            self.tr(u'Paint districts'),
            callback=self.startPaintDistricts,
            enabledFlag=False,
            parent=self.iface.mainWindow()
        )

        self.actionCommitPlanChanges = self.addAction(
            QgsApplication.getThemeIcon('/mActionSaveAllEdits.svg'),
            text=self.tr(u'Commit changes'),
            statusTip=self.tr(
                u'Save all districting changes to the underlying layer'),
            callback=self.onCommitChanges,
            enabledFlag=False,
            parent=self.iface.mainWindow()
        )

        self.actionRollbackPlanChanges = self.addAction(
            QgsApplication.getThemeIcon('/mActionCancelEdits.svg'),
            text=self.tr(u'Rollback changes'),
            statusTip=self.tr(
                u'Discard all unsaved districting changes'),
            callback=self.onRollbackChanges,
            enabledFlag=False,
            parent=self.iface.mainWindow()
        )

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
            self.project.layersAdded.disconnect(self.onLayersAdded)
            self.project.layersWillBeRemoved.disconnect(self.onLayersWillBeRemoved)
            self.project.layersRemoved.disconnect(self.onLayersRemoved)
            self.project.removeAll.disconnect(self.onCloseProject)
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

        for action in self.actions:
            self.iface.removePluginVectorMenu(self.menuName, action)
            self.iface.removeToolBarIcon(action)

        self.iface.removePluginVectorMenu(self.menuName, self.toolBtnAction)

        # remove the toolbar
        del self.toolbar

    def setupToolboxDockWidget(self):
        """Create the dockwidget with tools for painting districts."""
        dockwidget = DockRedistrictingToolbox(self.activePlan)

        dockwidget.geoFieldChanged.connect(self.geoFieldChanged)
        dockwidget.targetChanged.connect(self.distTargetChanged)
        dockwidget.sourceChanged.connect(self.distSourceChanged)
        dockwidget.btnAssign.setDefaultAction(self.actionStartPaintDistricts)
        dockwidget.btnCommitUpdate.setDefaultAction(self.actionCommitPlanChanges)
        dockwidget.btnRollbackUpdate.setDefaultAction(self.actionRollbackPlanChanges)
        dockwidget.btnEditPlan.setDefaultAction(self.actionEditPlan)

        self.iface.addDockWidget(Qt.RightDockWidgetArea, dockwidget)

        self.addAction(
            ':/plugins/redistricting/paintdistricts.svg',
            text=self.tr(u'Paint Districts'),
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
            text=self.tr(u'District Data'),
            statusTip=self.tr(
                u'Show/hide district demographic data/metrics table'),
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
            text=self.tr(u'Pending Changes'),
            statusTip=self.tr(u'Show/hide pending changes dock widget'),
            addToToolbar=True,
            addToMenu=True,
            callback=dockwidget.toggleViewAction(),
            parent=self.iface.mainWindow())

        dockwidget.hide()
        return dockwidget

    def checkActivePlan(self, action):
        if self.activePlan is None:
            self.iface.messageBar().pushMessage(
                self.tr("Oops!"),
                self.tr(f"Cannot {action}: no active redistricting plan. Try creating a new plan."),
                level=Qgis.Warning
            )
            return False

        return True

    # --------------------------------------------------------------------------

    def progressCanceled(self):
        """Hide progress dialog and display message on cancel"""

        if self.activePlan and self.activePlan.error():
            error, level = self.activePlan.error()
        else:
            level = None
        if level == Qgis.UserCanceled:
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
            except:
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

    # --------------------------------------------------------------------------

    def onReadProject(self, doc: QDomDocument, context: QgsReadWriteContext):
        self.clear()
        storage = ProjectStorage(self.project, doc, context)
        self.redistrictingPlans.extend(storage.readRedistrictingPlans())
        for plan in self.redistrictingPlans:
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
        for plan in self.redistrictingPlans:
            storage.writePlan(plan)
            if self.activePlan == plan:
                storage.writeActivePlan(plan)

    def onLayersWillBeRemoved(self, layerIds):
        if self.projectClosing:
            self.projectClosing = False
        else:
            deletePlans = set()
            for plan in self.redistrictingPlans:
                for layer in layerIds:
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

    def onLayersAdded(self, layers):  # pylint: disable=unused-argument
        if self.actionNewPlan.isEnabled():
            return

        self.actionNewPlan.setEnabled(
            any(isinstance(layer, QgsVectorLayer)
                for layer in self.project.mapLayers(True).values())
        )

    def onLayersRemoved(self, layers):
        self.actionNewPlan.setEnabled(
            any(isinstance(layer, QgsVectorLayer)
                for layer in self.project.mapLayers(True).values())
        )

    def onCloseProject(self):
        self.projectClosing = True
        self.clear()
        self.dockwidget.hide()
        self.dataTableWidget.hide()

    def geoFieldChanged(self, field):
        self.geoSelectField = field

    def distSourceChanged(self, source):
        self.distSource = source if source >= 0 else None

    def distTargetChanged(self, target):
        if target == -1:
            self.distTarget = self.createDistrict()
        elif target >= 0:
            self.distTarget = target
        if self.distTarget is None:
            self.canvas.unsetMapTool(self.mapTool)

    def startPaintDistricts(self):
        if self.activePlan:
            if self.distTarget is None:
                self.distTarget = self.createDistrict()
            if self.distTarget is not None:
                self.canvas.setMapTool(self.mapTool)
            self.assignmentEditor = PlanAssignmentEditor(self.activePlan, self.activePlan)

    def onPaintDistrict(self, feature: QgsFeature):
        if self.geoSelectField is None or self.geoSelectField == self.activePlan.geoIdField:
            features = {feature.id(): feature}
        else:
            value = str(feature.attribute(self.geoSelectField))
            features = self.assignmentEditor.getDistFeatures(
                self.geoSelectField, value, self.distSource)

        feedback = QgsFeedback()
        feedback.progressChanged.connect(
            lambda p: self.iface.statusBarIface().showMessage(
                f'painted {p} {self.activePlan.geoDisplay.lower()}s')
        )

        self.assignmentEditor.assignFeaturesToDistrict(
            features, self.distTarget, self.distSource)
        self.activePlan.assignLayer.triggerRepaint()

    def onCommitChanges(self):
        self.assignmentEditor.commitChanges()

    def onRollbackChanges(self):
        self.assignmentEditor.rollback()
        self.activePlan.assignLayer.triggerRepaint()

    def showPlanManager(self):
        """Display the plan manager window"""
        dlg = DlgSelectPlan(self.redistrictingPlans, self.activePlan)
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
            dlgEditPlan.updatePlan(plan)
            self.project.setDirty()

    def deletePlan(self, plan: RedistrictingPlan):
        if plan in self.redistrictingPlans:
            dlg = DlgConfirmDelete(plan)
            if dlg.exec_() == QDialog.Accepted:
                self.removePlan(plan, dlg.removeLayers(), dlg.deleteGeoPackage())

    def createPlanGeoPackage(
        self,
        plan: RedistrictingPlan,
        path: str,
        srcLayer=None,
        srcGeoId=None,
        importPlan=False,
        importPath=None,
        importField=None,
        headerRow=False,
        geoCol=0,
        distCol=1,
        delim=',',
        quote='"'
    ):
        def layersCreated(plan: RedistrictingPlan):
            if importPlan:
                importer = PlanImporter(plan)
                importer.importComplete.connect(plan.assignLayer.triggerRepaint)
                importer.importAssignments(
                    importPath,
                    importField,
                    headerRow,
                    geoCol,
                    distCol,
                    delim,
                    quote,
                    self.startProgress(self.tr('Importing assignments...'))
                )

            PlanStyler.style(plan, self.activePlan)
            self.iface.layerTreeView().refreshLayerSymbology(plan.distLayer.id())
            self.iface.layerTreeView().refreshLayerSymbology(plan.assignLayer.id())

            self.appendPlan(plan)
            self.setActivePlan(plan)

        plan.layersCreated.connect(layersCreated)
        plan.createLayers(path, srcLayer, srcGeoId, self.startProgress(self.tr('Creating plan layers...')))

    def newPlan(self):
        """Display new redistricting plan dialog and create new plan"""

        if len(self.project.mapLayers()) == 0:
            self.iface.messageBar().pushMessage(
                self.tr("Oops!"), self.tr(u"Cannot create a redistricting plan for an \
                    empty project. Try adding some layers."), level=Qgis.Warning)
            return

        dlgNewPlan = DlgEditPlan()
        if dlgNewPlan.exec_() == QDialog.Accepted:
            plan = dlgNewPlan.createPlan()
            self.createPlanGeoPackage(plan, dlgNewPlan.gpkgPath(),
                                      dlgNewPlan.sourceLayer(),
                                      dlgNewPlan.geoIdField(),
                                      dlgNewPlan.importPlan(),
                                      dlgNewPlan.importPath(),
                                      dlgNewPlan.importField(),
                                      dlgNewPlan.importHeaderRow(),
                                      dlgNewPlan.importGeoCol(),
                                      dlgNewPlan.importDistCol(),
                                      dlgNewPlan.importDelim(),
                                      dlgNewPlan.importQuote())

    def copyPlan(self):
        if not self.checkActivePlan(self.tr('copy')):
            return

        dlgCopyPlan = DlgCopyPlan(self.activePlan)
        if dlgCopyPlan.exec_() == QDialog.Accepted:
            copier = PlanCopier(self.activePlan)
            if not dlgCopyPlan.copyAssignments:
                copier.copyComplete.connect(lambda p: self.createPlanGeoPackage(p, dlgCopyPlan.geoPackagePath))
            plan = copier.copyPlan(dlgCopyPlan.planName, dlgCopyPlan.copyAssignments, dlgCopyPlan.geoPackagePath)
            self.appendPlan(plan)
            self.setActivePlan(plan)

    def importPlan(self):
        if not self.checkActivePlan(self.tr('import')):
            return

        dlgImportPlan = DlgImportPlan(self.activePlan)
        if dlgImportPlan.exec_() == QDialog.Accepted:
            importer = PlanImporter(self.activePlan)
            importer.importComplete.connect(self.activePlan.assignLayer.triggerRepaint)
            importer.importAssignments(
                dlgImportPlan.equivalencyFileName,
                dlgImportPlan.joinField,
                dlgImportPlan.headerRow,
                dlgImportPlan.geoColumn,
                dlgImportPlan.distColumn,
                dlgImportPlan.delimiter,
                dlgImportPlan.quotechar,
                self.startProgress(self.tr('Importing assignments...'))
            )

    def importShapefile(self):
        if not self.checkActivePlan(self.tr('import')):
            return

        dlgImportPlan = DlgImportShape(self.activePlan)
        if dlgImportPlan.exec_() == QDialog.Accepted:
            importer = PlanImporter(self.activePlan)
            importer.importComplete.connect(self.activePlan.assignLayer.triggerRepaint)
            importer.importShapefile(
                dlgImportPlan.shapefileFileName,
                dlgImportPlan.distField,
                dlgImportPlan.nameField,
                dlgImportPlan.membersField,
                self.startProgress(self.tr('Importing shapefile...'))
            )

    def exportPlan(self):
        def planExported(plan: RedistrictingPlan):
            self.iface.messageBar().pushMessage(
                "Success", f"Export of {plan.name} complete!", level=Qgis.Success)

        if not self.checkActivePlan(self.tr('export')):
            return

        dlgExportPlan = DlgExportPlan(self.activePlan)
        if dlgExportPlan.exec_() == QDialog.Accepted:
            if dlgExportPlan.exportEquivalency or dlgExportPlan.exportShapefile:
                export = PlanExporter(self.activePlan,
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

    def planChanged(self, plan, prop, newValue, oldValue):
        self.project.setDirty()
        if prop in ['total-population', 'pop-field', 'vap-field', 'cvap-field', 'data-fields']:
            self.dataTableWidget.tblDataTable.update()

    def createDistrict(self):
        if self.activePlan.allocatedDistricts == self.activePlan.numDistricts:
            QgsMessageLog.logMessage(
                self.tr('All districts have already been allocated'), 'Redistricting')
            self.distTarget = None
            return

        dlg = DlgNewDistrict(self.activePlan)
        if dlg.exec_() == QDialog.Accepted:
            dist = self.activePlan.addDistrict(
                dlg.districtNumber, dlg.districtName, dlg.members, dlg.description)
            self.dockwidget.setTargetDistrict(dist)
            return dist.district
        else:
            return None

    # --------------------------------------------------------------------------

    def appendPlan(self, plan: RedistrictingPlan):
        self.redistrictingPlans.append(plan)
        plan.planChanged.connect(self.planChanged)
        self.project.setDirty()

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
                for i in glob(f'{path}*'):
                    os.unlink(i)

            self.project.setDirty()

    def clear(self):
        self.setActivePlan(None)
        self.redistrictingPlans.clear()
        if not self.projectClosing:
            self.actionNewPlan.setEnabled(
                any(isinstance(layer, QgsVectorLayer)
                    for layer in self.project.mapLayers(True).values())
            )

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

            self.distTarget = None
            self.distSource = None
            self.geoSelectField = None
            self.dockwidget.plan = self.activePlan
            self.dataTableWidget.plan = self.activePlan
            self.pendingChangesWidget.plan = self.activePlan

            if self.activePlan and self.activePlan.assignLayer:
                self.mapTool = PaintDistrictsTool(
                    self.canvas, self.activePlan.assignLayer)
                self.mapTool.featureIdentified.connect(self.onPaintDistrict)

                self.activePlan.assignLayer.editingStarted.connect(
                    self.editingStarted)
                self.activePlan.assignLayer.editingStopped.connect(
                    self.editingStopped)

                self.actionCommitPlanChanges.setEnabled(
                    self.activePlan.assignLayer and self.activePlan.assignLayer.isEditable())
                self.actionRollbackPlanChanges.setEnabled(
                    self.activePlan.assignLayer and self.activePlan.assignLayer.isEditable())
            else:
                if self.mapTool:
                    self.mapTool = None
                    self.canvas.setMapTool(
                        QgsMapToolIdentifyFeature(
                            self.canvas, self.iface.activeLayer())
                    )

            self.actionStartPaintDistricts.setEnabled(
                self.activePlan is not None)
            self.actionEditPlan.setEnabled(self.activePlan is not None)
            self.actionImportAssignments.setEnabled(
                self.activePlan is not None)
            self.actionImportShapefile.setEnabled(
                self.activePlan is not None)
            self.actionExportPlan.setEnabled(self.activePlan is not None)
            self.actionCopyPlan.setEnabled(self.activePlan is not None)
