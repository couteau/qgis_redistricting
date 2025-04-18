# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin

        QGIS plugin for building political districts from geographic units
        (Originally generated using Plugin Builder bygsherman@geoapt.com
        and then heavily modified)

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022-2024 by Cryptodira
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

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsProject,
    QgsProjectDirtyBlocker,
    QgsReadWriteContext
)
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QSettings,
    QTranslator
)
from qgis.PyQt.QtWidgets import (
    QMenu,
    QToolBar
)
from qgis.PyQt.QtXml import QDomDocument

from .resources import *  # pylint: disable=wildcard-import,unused-wildcard-import

# pylint: disable=wrong-import-position
# isort: off
from .gui.settings import RdsOptionsFactory
from .controllers import (
    ContextMenuController,
    DistrictController,
    EditAssignmentsController,
    MetricsController,
    PendingChangesController,
    PlanController
)
from .services import (
    ActionRegistry,
    AssignmentsService,
    DeltaUpdateService,
    DistrictCopier,
    DistrictUpdater,
    LayerTreeManager,
    PlanImportService,
    PlanManager,
    PlanStylerService,
    ProjectStorage
)


class Redistricting:
    """QGIS Redistricting Plugin"""

    def __init__(self, iface: QgisInterface):
        self.name = self.__class__.__name__
        self.iface = iface
        self.canvas = self.iface.mapCanvas()

        self.actionRegistry = ActionRegistry()

        self.unloading = False
        self.project = QgsProject.instance()
        self.projectClosing = False

        # initialize plugin directory
        self.pluginDir = pathlib.Path(__file__).parent

        if not hasattr(Qgis, 'UserCanceled'):
            Qgis.UserCanceled = Qgis.MessageLevel.Success + 0x100

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        localePath = self.pluginDir / 'i18n' / f'{self.name}_{locale}.qm'

        if localePath.exists():
            self.translator = QTranslator()
            self.translator.load(str(localePath))
            QCoreApplication.installTranslator(self.translator)

        self.optionsFactory: RdsOptionsFactory

        # set up services
        self.planManager = PlanManager()
        self.layerTreeManger = LayerTreeManager()
        self.planStyler = PlanStylerService(self.planManager)
        self.deltaService = DeltaUpdateService(self.planManager)
        self.updaterService = DistrictUpdater()
        self.importService = PlanImportService()
        self.importService.importComplete.connect(
            lambda plan: self.updaterService.updateDistricts(
                plan, needDemographics=True, needGeometry=True, needSplits=True, force=True
            )
        )
        self.assignmentsService = AssignmentsService()
        self.districtCopier = DistrictCopier(iface, self.planManager, self.assignmentsService)

        # create toolbar
        self.toolbar: QToolBar = QToolBar(self.name)
        self.toolbar.setObjectName(self.name)

        # create controllers - no fancy dependency injection; we do it mannually
        self.planController = PlanController(
            self.iface,
            self.project,
            self.planManager,
            self.toolbar,
            self.layerTreeManger,
            self.planStyler,
            self.updaterService,
            self.importService
        )

        self.editController = EditAssignmentsController(
            self.iface,
            self.project,
            self.planManager,
            self.toolbar,
            self.assignmentsService
        )

        self.metricsController = MetricsController(
            self.iface,
            self.project,
            self.planManager,
            self.toolbar,
            self.updaterService
        )

        self.districtController = DistrictController(
            self.iface,
            self.project,
            self.planManager,
            self.toolbar,
            self.assignmentsService,
            self.districtCopier,
            self.updaterService
        )

        self.pendingController = PendingChangesController(
            self.iface,
            self.project,
            self.planManager,
            self.toolbar,
            self.deltaService
        )

        self.contextConroller = ContextMenuController(
            self.iface,
            self.project,
            self.planManager,
            self.toolbar,
            self.planController
        )

    @staticmethod
    def tr(message):
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('redistricting', message)

    def initGui(self):
        """Create the menu entries, toolbar buttons, actions, and dock widgets."""
        QgsApplication.instance().aboutToQuit.connect(self.onQuit)

        self.project.readProjectWithContext.connect(self.onReadProject)
        self.project.writeProject.connect(self.onWriteProject)

        if Qgis.versionInt() < 33400:
            # prior to v. 3.34, there is no signal that gets triggered
            # before a project is closed, but removeAll comes close
            self.project.removeAll.connect(self.onProjectClosing)
        else:
            self.project.aboutToBeCleared.connect(self.onProjectClosing)

        self.project.cleared.connect(self.onProjectClosed)

        # layerWillBeRemoved signal is triggered when a project is
        # closed or when the user removes a layer, and there seems
        # to be no way to disinguish. We use a flag set in the
        # signal handler for the project aboutToBeCleared (or, in
        # versions before 3.34, removeAll) signal to ignore this
        # signal when triggered in the context of a project closing
        self.project.layerWillBeRemoved.connect(self.onLayerWillBeRemoved)

        self.iface.addToolBar(self.toolbar)

        self.planController.load()
        self.editController.load()
        self.metricsController.load()
        self.districtController.load()
        self.pendingController.load()
        self.contextConroller.load()

        self.optionsFactory = RdsOptionsFactory()
        self.optionsFactory.setTitle(self.name)
        self.iface.registerOptionsWidgetFactory(self.optionsFactory)

        self.unloading = False

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self.unloading = True

        self.iface.unregisterOptionsWidgetFactory(self.optionsFactory)

        self.project.readProjectWithContext.disconnect(self.onReadProject)
        self.project.writeProject.disconnect(self.onWriteProject)
        if Qgis.versionInt() < 33400:
            # prior to v. 3.34, there is no signal that gets triggered
            # before a project is closed, but removeAll comes close
            self.project.removeAll.disconnect(self.onProjectClosing)
        else:
            self.project.cleared.disconnect(self.onProjectClosed)

        self.project.aboutToBeCleared.disconnect(self.onProjectClosing)
        self.project.layerWillBeRemoved.disconnect(self.onLayerWillBeRemoved)

        QgsApplication.instance().aboutToQuit.disconnect(self.onQuit)

        self.contextConroller.unload()
        self.pendingController.unload()
        self.districtController.unload()
        self.metricsController.unload()
        self.editController.unload()
        self.planController.unload()

        # iface.addToolBar adds the toolbar to the View|Toolbars menu,
        # but iface has no removeToolBar method, so we need another way
        toolbarMenu = self.iface.mainWindow().findChild(QMenu, 'mToolbarMenu')
        if toolbarMenu is not None:
            toolbarMenu.removeAction(self.toolbar.toggleViewAction())
        self.iface.mainWindow().removeToolBar(self.toolbar)
        self.toolbar.hide()
        self.toolbar.setParent(None)

    # --------------------------------------------------------------------------

    def onQuit(self):
        self.unloading = True

    def onReadProject(self, doc: QDomDocument, context: QgsReadWriteContext):
        dirtyBlocker = QgsProjectDirtyBlocker(self.project)
        try:
            self.clear()
            storage = ProjectStorage(self.project, doc, context)
            self.planManager.extend(storage.readRedistrictingPlans())

            if len(self.planManager) == 1:
                self.planManager.setActivePlan(self.planManager[0])
            else:
                uuid = storage.readActivePlan()
                if uuid:
                    self.planManager.setActivePlan(uuid)
                elif len(self.planManager) != 0:
                    self.planManager.setActivePlan(self.planManager[0])
        finally:
            del dirtyBlocker

    def onWriteProject(self, doc: QDomDocument):
        if len(self.planManager) == 0:
            return

        dirtyBlocker = QgsProjectDirtyBlocker(self.project)
        try:
            rg = self.project.layerTreeRoot()
            rg.setHasCustomLayerOrder(False)
        finally:
            del dirtyBlocker

        storage = ProjectStorage(self.project, doc)
        storage.writeRedistrictingPlans(self.planManager)
        storage.writeActivePlan(self.planManager.activePlan)

    def onProjectClosing(self):
        if self.unloading:
            return

        self.projectClosing = True
        self.clear()

    def onProjectClosed(self):
        self.projectClosing = False

    def onLayerWillBeRemoved(self, layerid):
        # TODO: move to PlanManager?
        if self.projectClosing or self.unloading:
            return

        layer = self.project.mapLayer(layerid)
        deletePlans = {
            plan for plan in self.planManager
            if layer in (plan.geoLayer, plan.popLayer, plan.assignLayer, plan.distLayer)
        }

        for plan in deletePlans:
            self.planManager.removePlan(plan)
            self.project.setDirty()

    # --------------------------------------------------------------------------

    def clear(self):
        self.planManager.clear()
