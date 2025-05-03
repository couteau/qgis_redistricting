"""QGIS Redistricting Plugin - test fixtures

Copyright 2022-2024, Stuart C. Naifeh

QGIS app fixtures, Copyright (C) 2021-2023 pytest-qgis Contributors, used
and modified under GNU General Public License version 3


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
import pathlib
import shutil
import tempfile
import unittest.mock
from typing import Optional, Union, overload
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsLayerTree,
    QgsMapLayer,
    QgsProject,
    QgsRelationManager,
    QgsVectorLayer,
)
from qgis.gui import (
    QgisInterface,
    QgsLayerTreeMapCanvasBridge,
    QgsLayerTreeView,
    QgsMapCanvas,
)
from qgis.PyQt import sip
from qgis.PyQt.QtCore import QObject, QSize, pyqtBoundSignal, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QAction,
    QActionGroup,
    QMainWindow,
    QMenu,
    QToolBar,
    QWidget,
)
from qgis.utils import iface  # pylint: disable=unused-import

# pylint: disable=redefined-outer-name

class MockMessageBar(QObject):
    """Mocked message bar to hold the messages."""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.messages: dict[int, list[str]] = {
            Qgis.MessageLevel.Info: [],
            Qgis.MessageLevel.Warning: [],
            Qgis.MessageLevel.Critical: [],
            Qgis.MessageLevel.Success: [],
        }

    def get_messages(self, level: int) -> list[str]:
        """Used to test which messages have been logged."""
        return self.messages[level]

    @overload
    def pushMessage(  # noqa: N802
        self,
        text: str,
        level: int = Qgis.MessageLevel.Info,
        duration: int = -1,  # noqa: ARG002
    ) -> None:
        ...

    @overload
    def pushMessage(
        self,
        title: str,
        text: str,
        level: int = Qgis.MessageLevel.Info,
        duration: int = -1
    ) -> None:
        ...

    @overload
    def pushMessage(  # noqa: N802
        self,
        title: str,
        text: str,
        showMore: Optional[str] = None,
        level: int = Qgis.MessageLevel.Info,
        duration: int = -1,  # noqa: ARG002
    ) -> None:
        ...

    def pushMessage(  # noqa: N802
        self,
        title: str,
        message: Union[str, int],
        showMore: Union[str, int, None] = None,
        level: int = Qgis.MessageLevel.Info,
        duration: int = -1,  # noqa: ARG002
    ) -> None:
        """A mocked method for pushing a message to the bar."""
        if isinstance(message, int):
            title = ""
            level = message or level
            duration = showMore or duration
            text = title
        else:
            text = message
            if not isinstance(showMore, str):
                level = showMore or level
                duration = level
                showMore = None

        msg = f"{title}:{text}"
        self.messages[level].append(msg)

    def pushCritical(self, title: str, message: str):
        self.pushMessage(title, message, Qgis.MessageLevel.Critical)

    def pushInfo(self, title: str, message: str):
        self.pushMessage(title, message, Qgis.MessageLevel.Info)

    def pushSuccess(self, title: str, message: str):
        self.pushMessage(title, message, Qgis.MessageLevel.Success)

    def pushWarning(self, title: str, message: str):
        self.pushMessage(title, message, Qgis.MessageLevel.Warning)


class MockQgisInterface(QgisInterface):
    initializationCompleted = pyqtSignal()
    projectRead = pyqtSignal()
    newProjectCreated = pyqtSignal()
    layerSavedAs = pyqtSignal("PyQt_PyObject", str)
    currentLayerChanged = pyqtSignal()

    def __init__(self, canvas: QgsMapCanvas, parent: QMainWindow):
        super().__init__()
        self.setParent(parent)
        self._layers: list[QgsMapLayer] = []
        # unittest.mock.patch.object(canvas, 'layers', new=self.layers).start()

        self._canvases = [canvas]
        QgsProject.instance().legendLayersAdded.connect(self.addLayers)
        QgsProject.instance().layersRemoved.connect(self.removeLayers)
        QgsProject.instance().removeAll.connect(self.removeAllLayers)

        self._toolbars: dict[str, QToolBar] = {}
        self._layerTreeView = QgsLayerTreeView(parent)
        self._layerTreeView.currentLayerChanged.connect(self.currentLayerChanged)
        self._activeLayerId = None
        self._messageBar = MockMessageBar()

    def layerTreeView(self):
        return self._layerTreeView

    def mapCanvas(self):
        return self._canvases[0]

    def mapCanvases(self):
        return self._canvases

    def createNewMapCanvas(self, name: str):
        self._canvases.append(QgsMapCanvas(self.parent()))
        self._canvases[-1].setObjectName(name)
        return self._canvases[-1]

    def closeMapCanvas(self, name: str):
        canvas = self.parent().findChild(QgsMapCanvas, name)
        if canvas is not None:
            self._canvases.remove(canvas)
            canvas.hide()
            canvas.deleteLater()

    def messageBar(self):
        return self._messageBar

    def layers(self) -> list[QgsMapLayer]:
        """Get the list of layers in the canvas."""
        return self._layers

    # @pyqtSlot("QList<QgsMapLayer*>")
    def addLayers(self, layers: list[QgsMapLayer]) -> None:
        """Handle layers being added to the registry so they show up in canvas.

        :param layers: list<QgsMapLayer> list of map layers that were added

        .. note:: The QgsInterface api does not include this method,
            it is added here as a helper to facilitate testing.
        """
        self._layers.extend(layers)
        # self._canvases[0].setLayers(self._layers)

    # @pyqtSlot("QList<QString>")
    def removeLayers(self, layers: list[str] = None) -> None:
        if layers is None:
            return
        self._layers = [layer for layer in self._layers if not sip.isdeleted(layer) and layer.id() not in layers]
        # self._canvases[0].setLayers(self._layers)

    # @pyqtSlot()
    def removeAllLayers(self) -> None:
        """Remove layers from the canvas before they get deleted."""
        self._layers = []
        # if not sip.isdeleted(self._canvases[0]):
        #    self._canvases[0].setLayers(self._layers)

    def newProject(self, promptToSaveFlag: bool = False) -> None:  # pylint: disable=unused-argument
        """Create new project."""
        # noinspection PyArgumentList
        instance = QgsProject.instance()
        # instance.clear()
        instance.removeAllMapLayers()
        root: QgsLayerTree = instance.layerTreeRoot()
        root.removeAllChildren()
        relation_manager: QgsRelationManager = instance.relationManager()
        for relation in relation_manager.relations():
            relation_manager.removeRelation(relation)
        self._layers = []
        self.newProjectCreated.emit()
        return True

    def addVectorLayer(
        self, path: str, base_name: str, provider_key: str
    ) -> QgsVectorLayer:
        """Add a vector layer.

        :param path: Path to layer.
        :type path: str

        :param base_name: Base name for layer.
        :type base_name: str

        :param provider_key: Provider key e.g. 'ogr'
        :type provider_key: str
        """
        layer = QgsVectorLayer(path, base_name, provider_key)
        self.addLayers([layer])
        return layer

    def activeLayer(self) -> Optional[QgsMapLayer]:
        """Get pointer to the active layer (layer selected in the legend)."""
        return (
            QgsProject.instance().mapLayer(self._activeLayerId)
            if self._activeLayerId
            else None
        )

    def setActiveLayer(self, layer: QgsMapLayer) -> None:
        """
        Set the active layer (layer gets selected in the legend)
        """
        self._activeLayerId = layer.id()
        self.currentLayerChanged.emit()

    def iconSize(self) -> QSize:
        return QSize(24, 24)

    def mainWindow(self) -> QMainWindow:
        return self.parent()

    def addToolBar(self, toolbar: Union[str, QToolBar]) -> QToolBar:
        """Add toolbar with specified name.

        :param toolbar: Name for the toolbar or QToolBar object.
        """
        if isinstance(toolbar, str):
            name = toolbar
            _toolbar = QToolBar(name, parent=self.parent())
        else:
            name = toolbar.windowTitle()
            _toolbar = toolbar
        self._toolbars[name] = _toolbar
        return _toolbar

    def editableLayers(self, modified=False):
        return [l for l in self._layers if l.isEditable() and (l.isModified() or not modified)]

    layerTreeCanvasBridge = unittest.mock.MagicMock()

    zoomFull = unittest.mock.MagicMock()
    zoomToPrevious = unittest.mock.MagicMock()
    zoomToNext = unittest.mock.MagicMock()
    zoomToActiveLayer = unittest.mock.MagicMock()

    addRasterLayer = unittest.mock.MagicMock()
    addMeshLayer = unittest.mock.MagicMock()
    addVectorTileLayer = unittest.mock.MagicMock()
    addPointCloudLayer = unittest.mock.MagicMock()
    addTiledSceneLayer = unittest.mock.MagicMock()

    addPluginToMenu = unittest.mock.MagicMock()
    addToolBarIcon = unittest.mock.MagicMock()
    removeToolBarIcon = unittest.mock.MagicMock()

    projectMenu = unittest.mock.MagicMock(spec=QMenu)

    projectImportExportMenu = unittest.mock.MagicMock(spec=QMenu)
    addProjectImportAction = unittest.mock.MagicMock()
    removeProjectImportAction = unittest.mock.MagicMock()

    editMenu = unittest.mock.MagicMock(spec=QMenu)
    viewMenu = unittest.mock.MagicMock(spec=QMenu)
    layerMenu = unittest.mock.MagicMock(spec=QMenu)
    newLayerMenu = unittest.mock.MagicMock(spec=QMenu)
    addLayerMenu = unittest.mock.MagicMock(spec=QMenu)
    settingsMenu = unittest.mock.MagicMock(spec=QMenu)
    pluginMenu = unittest.mock.MagicMock(spec=QMenu)
    pluginHelpMenu = unittest.mock.MagicMock(spec=QMenu)
    rasterMenu = unittest.mock.MagicMock(spec=QMenu)
    databaseMenu = unittest.mock.MagicMock(spec=QMenu)
    vectorMenu = unittest.mock.MagicMock(spec=QMenu)
    firstRightStandardMenu = unittest.mock.MagicMock(spec=QMenu)
    windowMenu = unittest.mock.MagicMock(spec=QMenu)
    helpMenu = unittest.mock.MagicMock(spec=QMenu)

    fileToolBar = unittest.mock.MagicMock(spec=QToolBar)
    layerToolBar = unittest.mock.MagicMock(spec=QToolBar)
    dataSourceManagerToolBar = unittest.mock.MagicMock(spec=QToolBar)
    mapNavToolToolBar = unittest.mock.MagicMock(spec=QToolBar)
    digitizeToolBar = unittest.mock.MagicMock(spec=QToolBar)
    advancedDigitizeToolBar = unittest.mock.MagicMock(spec=QToolBar)
    shapeDigitizeToolBar = unittest.mock.MagicMock(spec=QToolBar)
    attributesToolBar = unittest.mock.MagicMock(spec=QToolBar)
    selectionToolBar = unittest.mock.MagicMock(spec=QToolBar)
    pluginToolBar = unittest.mock.MagicMock(spec=QToolBar)
    helpToolBar = unittest.mock.MagicMock(spec=QToolBar)
    rasterToolBar = unittest.mock.MagicMock(spec=QToolBar)
    vectorToolBar = unittest.mock.MagicMock(spec=QToolBar)
    databaseToolBar = unittest.mock.MagicMock(spec=QToolBar)
    webToolBar = unittest.mock.MagicMock(spec=QToolBar)

    mapToolActionGroup = unittest.mock.MagicMock(spec=QActionGroup)

    openDataSourceManagerPage = unittest.mock.MagicMock()

    addCustomActionForLayerType = unittest.mock.MagicMock()
    removeCustomActionForLayerType = unittest.mock.MagicMock()
    addCustomActionForLayer = unittest.mock.MagicMock()

    addPluginToVectorMenu = unittest.mock.MagicMock()
    removePluginVectorMenu = unittest.mock.MagicMock()

    addDockWidget = unittest.mock.MagicMock()
    removeDockWidget = unittest.mock.MagicMock()
    registerMainWindowAction = unittest.mock.MagicMock()
    unregisterMainWindowAction = unittest.mock.MagicMock()

    registerOptionsWidgetFactory = unittest.mock.MagicMock()
    unregisterOptionsWidgetFactory = unittest.mock.MagicMock()
    registerProjectPropertiesWidgetFactory = unittest.mock.MagicMock()
    unregisterProjectPropertiesWidgetFactory = unittest.mock.MagicMock()

    actionNewProject = unittest.mock.MagicMock(spec=QAction)
    actionOpenProject = unittest.mock.MagicMock(spec=QAction)
    actionSaveProject = unittest.mock.MagicMock(spec=QAction)
    actionSaveProjectAs = unittest.mock.MagicMock(spec=QAction)
    actionSaveMapAsImage = unittest.mock.MagicMock(spec=QAction)
    actionProjectProperties = unittest.mock.MagicMock(spec=QAction)
    actionCreatePrintLayout = unittest.mock.MagicMock(spec=QAction)
    actionShowLayoutManager = unittest.mock.MagicMock(spec=QAction)
    actionExit = unittest.mock.MagicMock(spec=QAction)
    actionCutFeatures = unittest.mock.MagicMock(spec=QAction)
    actionCopyFeatures = unittest.mock.MagicMock(spec=QAction)
    actionPasteFeatures = unittest.mock.MagicMock(spec=QAction)
    actionAddFeature = unittest.mock.MagicMock(spec=QAction)
    actionDeleteSelected = unittest.mock.MagicMock(spec=QAction)
    actionMoveFeature = unittest.mock.MagicMock(spec=QAction)
    actionSplitFeatures = unittest.mock.MagicMock(spec=QAction)
    actionSplitParts = unittest.mock.MagicMock(spec=QAction)
    actionAddRing = unittest.mock.MagicMock(spec=QAction)
    actionAddPart = unittest.mock.MagicMock(spec=QAction)
    actionSimplifyFeature = unittest.mock.MagicMock(spec=QAction)
    actionDeleteRing = unittest.mock.MagicMock(spec=QAction)
    actionDeletePart = unittest.mock.MagicMock(spec=QAction)
    actionVertexTool = unittest.mock.MagicMock(spec=QAction)
    actionVertexToolActiveLayer = unittest.mock.MagicMock(spec=QAction)

    actionPan = unittest.mock.MagicMock(spec=QAction)
    actionPanToSelected = unittest.mock.MagicMock(spec=QAction)
    actionZoomIn = unittest.mock.MagicMock(spec=QAction)
    actionZoomOut = unittest.mock.MagicMock(spec=QAction)
    actionSelect = unittest.mock.MagicMock(spec=QAction)
    actionSelectRectangle = unittest.mock.MagicMock(spec=QAction)
    actionSelectPolygon = unittest.mock.MagicMock(spec=QAction)
    actionSelectFreehand = unittest.mock.MagicMock(spec=QAction)
    actionSelectRadius = unittest.mock.MagicMock(spec=QAction)
    actionIdentify = unittest.mock.MagicMock(spec=QAction)
    actionFeatureAction = unittest.mock.MagicMock(spec=QAction)
    actionMeasure = unittest.mock.MagicMock(spec=QAction)
    actionMeasureArea = unittest.mock.MagicMock(spec=QAction)

    actionZoomFullExtent = unittest.mock.MagicMock(spec=QAction)
    actionZoomToLayers = unittest.mock.MagicMock(spec=QAction)
    actionZoomToSelected = unittest.mock.MagicMock(spec=QAction)
    actionZoomLast = unittest.mock.MagicMock(spec=QAction)
    actionZoomNext = unittest.mock.MagicMock(spec=QAction)
    actionZoomActualSize = unittest.mock.MagicMock(spec=QAction)
    actionMapTips = unittest.mock.MagicMock(spec=QAction)
    actionNewBookmark = unittest.mock.MagicMock(spec=QAction)
    actionShowBookmarks = unittest.mock.MagicMock(spec=QAction)
    actionDraw = unittest.mock.MagicMock(spec=QAction)
    actionNewVectorLayer = unittest.mock.MagicMock(spec=QAction)
    actionAddOgrLayer = unittest.mock.MagicMock(spec=QAction)
    actionAddRasterLayer = unittest.mock.MagicMock(spec=QAction)
    actionAddPgLayer = unittest.mock.MagicMock(spec=QAction)
    actionAddWmsLayer = unittest.mock.MagicMock(spec=QAction)
    actionAddXyzLayer = unittest.mock.MagicMock(spec=QAction)
    actionAddVectorTileLayer = unittest.mock.MagicMock(spec=QAction)
    actionAddPointCloudLayer = unittest.mock.MagicMock(spec=QAction)
    actionAddAfsLayer = unittest.mock.MagicMock(spec=QAction)
    actionAddAmsLayer = unittest.mock.MagicMock(spec=QAction)
    actionCopyLayerStyle = unittest.mock.MagicMock(spec=QAction)
    actionPasteLayerStyle = unittest.mock.MagicMock(spec=QAction)
    actionOpenTable = unittest.mock.MagicMock(spec=QAction)
    actionOpenFieldCalculator = unittest.mock.MagicMock(spec=QAction)
    actionOpenStatisticalSummary = unittest.mock.MagicMock(spec=QAction)
    actionToggleEditing = unittest.mock.MagicMock(spec=QAction)
    actionSaveActiveLayerEdits = unittest.mock.MagicMock(spec=QAction)
    actionAllEdits = unittest.mock.MagicMock(spec=QAction)
    actionSaveEdits = unittest.mock.MagicMock(spec=QAction)
    actionSaveAllEdits = unittest.mock.MagicMock(spec=QAction)
    actionRollbackEdits = unittest.mock.MagicMock(spec=QAction)
    actionRollbackAllEdits = unittest.mock.MagicMock(spec=QAction)
    actionCancelEdits = unittest.mock.MagicMock(spec=QAction)
    actionCancelAllEdits = unittest.mock.MagicMock(spec=QAction)
    actionLayerSaveAs = unittest.mock.MagicMock(spec=QAction)
    actionDuplicateLayer = unittest.mock.MagicMock(spec=QAction)
    actionLayerProperties = unittest.mock.MagicMock(spec=QAction)
    actionAddToOverview = unittest.mock.MagicMock(spec=QAction)
    actionAddAllToOverview = unittest.mock.MagicMock(spec=QAction)
    actionRemoveAllFromOverview = unittest.mock.MagicMock(spec=QAction)
    actionHideAllLayers = unittest.mock.MagicMock(spec=QAction)
    actionShowAllLayers = unittest.mock.MagicMock(spec=QAction)
    actionHideSelectedLayers = unittest.mock.MagicMock(spec=QAction)
    actionToggleSelectedLayers = unittest.mock.MagicMock(spec=QAction)
    actionToggleSelectedLayersIndependently = unittest.mock.MagicMock(spec=QAction)
    actionHideDeselectedLayers = unittest.mock.MagicMock(spec=QAction)
    actionShowSelectedLayers = unittest.mock.MagicMock(spec=QAction)
    actionManagePlugins = unittest.mock.MagicMock(spec=QAction)
    actionPluginListSeparator = unittest.mock.MagicMock(spec=QAction)
    actionShowPythonDialog = unittest.mock.MagicMock(spec=QAction)
    actionToggleFullScreen = unittest.mock.MagicMock(spec=QAction)
    actionOptions = unittest.mock.MagicMock(spec=QAction)
    actionCustomProjection = unittest.mock.MagicMock(spec=QAction)
    actionHelpContents = unittest.mock.MagicMock(spec=QAction)
    actionQgisHomePage = unittest.mock.MagicMock(spec=QAction)
    actionCheckQgisVersion = unittest.mock.MagicMock(spec=QAction)
    actionAbout = unittest.mock.MagicMock(spec=QAction)


profileDir = tempfile.mkdtemp(prefix='qgis_test_')
_APP = QgsApplication([], True, profileDir)
_APP.initQgis()

_CANVAS: QgsMapCanvas = None
_PARENT: QWidget = None
_IFACE: QgisInterface = None

_PARENT = QMainWindow()
_CANVAS = QgsMapCanvas()
_PARENT.setCentralWidget(_CANVAS)
_IFACE = MockQgisInterface(_CANVAS, _PARENT)

unittest.mock.patch("qgis.utils.iface", _IFACE).start()


@pytest.fixture(scope='session', autouse=True)
def qgis_app():
    """QGIS application fixture."""
    global _CANVAS, _PARENT, _IFACE  # pylint: disable=global-statement

    QgsProject.instance().legendLayersAdded.connect(_APP.processEvents)

    yield _APP

    QgsProject.instance().legendLayersAdded.disconnect(_APP.processEvents)

    if os.path.exists(profileDir):
        shutil.rmtree(profileDir, ignore_errors=True)

    _APP.exitQgis()


@pytest.fixture(scope="session")
def qapp_cls():
    return QgsApplication


@pytest.fixture(scope="session")
def qapp(qgis_app):
    return qgis_app


@pytest.fixture
def mock_taskmanager(qgis_app: QgsApplication, mocker: MockerFixture):
    """Mock the task manager."""
    addTask = mocker.patch.object(qgis_app.taskManager(), "addTask")
    addTask.return_value = 0
    return addTask


@pytest.fixture(scope='session')
def qgis_canvas_session(qgis_app):  # pylint: disable=unused-argument
    return _CANVAS


@pytest.fixture
def qgis_canvas(qgis_canvas_session):  # pylint: disable=unused-argument
    bridge = QgsLayerTreeMapCanvasBridge(QgsProject.instance().layerTreeRoot(), _CANVAS)
    yield qgis_canvas_session
    bridge.deleteLater()


@pytest.fixture(scope='session')
def qgis_parent(qgis_app):  # pylint: disable=unused-argument
    return _PARENT


@pytest.fixture(scope='session')
def qgis_iface(qgis_app):  # pylint: disable=unused-argument
    return _IFACE


@pytest.fixture(scope='function', autouse=True)
def new_project(qgis_app):  # pylint: disable=unused-argument
    QgsProject.instance().clear()


@pytest.fixture
def datadir(tmp_path: pathlib.Path):
    d = tmp_path / 'data'
    s = pathlib.Path(__file__).parent / 'data'
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(s, d)
    yield d
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture
def block_layer(datadir: pathlib.Path):
    gpkg = (datadir / 'tuscaloosa.gpkg').resolve()
    layer = QgsVectorLayer(f'{gpkg}|layername=block20', 'blocks', 'ogr')
    layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4269"), False)
    QgsProject.instance().addMapLayer(layer)
    return layer


@pytest.fixture
def vtd_layer(datadir: pathlib.Path):
    gpkg = (datadir / 'tuscaloosa.gpkg').resolve()
    layer = QgsVectorLayer(f'{gpkg}|layername=vtd20', 'vtd', 'ogr')
    layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4269"), False)
    QgsProject.instance().addMapLayer(layer)
    return layer


@pytest.fixture
def county_layer(datadir: pathlib.Path):
    gpkg = (datadir / 'tuscaloosa.gpkg').resolve()
    layer = QgsVectorLayer(f'{gpkg}|layername=county20', 'county', 'ogr')
    layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4269"), False)
    QgsProject.instance().addMapLayer(layer)
    return layer


@pytest.fixture
def related_layers(block_layer, vtd_layer, county_layer):
    for rel in QgsProject.instance().relationManager().discoverRelations([], [county_layer, vtd_layer, block_layer]):
        QgsProject.instance().relationManager().addRelation(rel)


@pytest.fixture
def plan_gpkg_path(datadir):
    return (datadir / 'tuscaloosa_plan.gpkg').resolve()


@pytest.fixture
def assign_layer(plan_gpkg_path):
    layer = QgsVectorLayer(
        f'{plan_gpkg_path}|layername=assignments', 'test_assignments', 'ogr')
    QgsProject.instance().addMapLayer(layer, False)
    return layer


@pytest.fixture
def dist_layer(plan_gpkg_path):
    layer = QgsVectorLayer(
        f'{plan_gpkg_path}|layername=districts', 'test_districts', 'ogr')
    QgsProject.instance().addMapLayer(layer, False)
    return layer


# pylint: disable=wrong-import-position
from redistricting.services.planbuilder import PlanBuilder  # isort:skip # nopep8
from redistricting.services.districtio import DistrictReader  # isort:skip # nopep8
from redistricting.models.plan import RdsPlan  # isort: skip # nopep8
from redistricting.models.base.serialization import deserialize  # isort: skip # nopep8
from redistricting.models import metrics, splitsmetric  # isort: skip # nopep8; pylint: disable=unused-import


@pytest.fixture
def minimal_plan():
    return RdsPlan('minimal', 5)


@pytest.fixture
def valid_plan(minimal_plan: RdsPlan, block_layer, plan_gpkg_path):
    minimal_plan.geoLayer = block_layer
    minimal_plan.geoIdField = 'geoid'
    minimal_plan.popField = 'pop_total'
    minimal_plan.addLayersFromGeoPackage(plan_gpkg_path)
    QgsProject.instance().addMapLayers([minimal_plan.distLayer, minimal_plan.assignLayer], False)
    return minimal_plan


@pytest.fixture
def plan(qgis_parent, block_layer, assign_layer, dist_layer):
    p: RdsPlan = deserialize(RdsPlan, {
        'name': 'test',
        'deviation': 0.025,
        'geo-layer': block_layer.id(),
        'geo-id-field': 'geoid',
        'dist-field': 'district',
        'pop-field': 'pop_total',
        'pop-fields': [
            {'layer': block_layer.id(),
                'field': 'vap_total',
                'caption': 'VAP'}
        ],
        'assign-layer': assign_layer.id(),
        'dist-layer': dist_layer.id(),
        'num-districts': 5,
        'data-fields': [
            {'layer': block_layer.id(),
                'field': 'vap_ap_black',
                'caption': 'APBVAP',
                'sum-field': True,
                'pct-base': 'vap_total'},
            {'layer': block_layer.id(),
                'field': 'vap_nh_white',
                'caption': 'WVAP',
                'sum-field': True,
                'pct-base': 'vap_total'},
            {'layer': block_layer.id(),
                'field': 'vap_hispanic',
                'caption': 'HVAP',
                'sum-field': True,
                'pct-base': 'vap_total'},
        ],
        'geo-fields': [
            {'layer': assign_layer.id(),
                'field': 'vtdid',
                'caption': 'VTD'}
        ],
        'metrics': { 'metrics': {
            'total-population': {'value': 227036},
            'plan-deviation': {'value': [100, -500]},
            'mean-polsbypopper': {'value': 0.4},
            'min-polsbypopper': {'value': 0.15},
            'max-polsbypopper': {'value': 0.8},
            'mean-reock': {'value': 0.5},
            'min-reock': {'value': 0.1},
            'max-reock': {'value': 0.9},
            'mean-convexhull': {'value': 0.5},
            'min-convexhull': {'value': 0.1},
            'max-convexhull': {'value': 0.9},
            'contiguity': {'value': True},
            'complete': {'value': True},
            'splits': {
                'value': {
                    'vtdid': {
                        'field': 'vtdid',
                        'caption': 'VTD',
                        'data': {
                            "schema": {"fields": [{"name": "index", "type": "integer"}], "primaryKey": ["index"], "pandas_version": "0.20.0"}, 
                            "data": []
                        }
                    }
                }
            }
        }}
    }, parent=qgis_parent)

    r = DistrictReader(dist_layer, popField='pop_total')
    for d in r.readFromLayer():
        if d.district == 0:
            p.districts[0].update(d)
        else:
            p.districts.append(d)

    return p


@pytest.fixture
def new_plan(block_layer: QgsVectorLayer, datadir: pathlib.Path):
    dst = datadir / 'tuscaloosa_new_plan.gpkg'

    b = PlanBuilder()
    p: RdsPlan = b \
        .setName('test') \
        .setNumDistricts(5) \
        .setDeviation(0.025) \
        .setGeoLayer(block_layer) \
        .setGeoIdField('geoid') \
        .setDistField('district') \
        .setPopField('pop_total') \
        .appendPopField('vap_total', caption='VAP') \
        .appendDataField('vap_nh_black', caption='BVAP') \
        .appendDataField('vap_ap_black', caption='APBVAP') \
        .appendDataField('vap_nh_white', caption='WVAP') \
        .appendGeoField('vtdid', caption='VTD') \
        .createPlan(createLayers=False)
    del b

    p.addLayersFromGeoPackage(dst)
    QgsProject.instance().addMapLayers([p.distLayer, p.assignLayer], False)
    p.metrics['totalPopulation']._value = 227036

    yield p

    p._setAssignLayer(None)  # pylint: disable=protected-access
    p._setDistLayer(None)  # pylint: disable=protected-access
    p.deleteLater()


@pytest.fixture
def mock_plan(mocker: MockerFixture) -> RdsPlan:
    mocker.patch('redistricting.models.plan.pyqtSignal', spec=pyqtBoundSignal)
    plan = mocker.create_autospec(
        spec=RdsPlan('mock_plan', 5),
        spec_set=True
    )
    type(plan).name = mocker.PropertyMock(return_value="test")
    type(plan).id = mocker.PropertyMock(return_value=uuid4())
    type(plan).description = mocker.PropertyMock(return_value="description")
    type(plan).assignLayer = mocker.PropertyMock(
        return_value=mocker.create_autospec(spec=QgsVectorLayer, instance=True))
    type(plan).distLayer = mocker.PropertyMock(return_value=mocker.create_autospec(spec=QgsVectorLayer, instance=True))
    type(plan).popLayer = mocker.PropertyMock(return_value=mocker.create_autospec(spec=QgsVectorLayer, instance=True))
    type(plan).geoLayer = mocker.PropertyMock(return_value=mocker.create_autospec(spec=QgsVectorLayer, instance=True))
    type(plan).distField = mocker.PropertyMock(return_value='district')
    type(plan).geoIdField = mocker.PropertyMock(return_value='geoid')
    type(plan).geoJoinField = mocker.PropertyMock(return_value='geoid')
    type(plan).popJoinField = mocker.PropertyMock(return_value='geoid')
    type(plan).popField = mocker.PropertyMock(return_value='pop_total')
    type(plan).numDistricts = mocker.PropertyMock(return_value=5)
    type(plan).numSeats = mocker.PropertyMock(return_value=5)
    type(plan).allocatedDistricts = mocker.PropertyMock(return_value=5)
    type(plan).allocatedSeats = mocker.PropertyMock(return_value=5)

    districts = mocker.create_autospec(spec=list, spec_set=True, instance=True)
    districts.__len__.return_value = 6
    type(plan).districts = mocker.PropertyMock(return_value=districts)

    pop_fields = mocker.create_autospec(spec=list, spec_set=True, instance=True)
    type(plan).popFields = mocker.PropertyMock(return_value=pop_fields)

    data_fields = mocker.create_autospec(spec=list, spec_set=True, instance=True)
    type(plan).dataFields = mocker.PropertyMock(return_value=data_fields)

    geo_fields = mocker.create_autospec(spec=list, spec_set=True, instance=True)
    type(plan).geoFields = mocker.PropertyMock(return_value=geo_fields)

    plan.assignLayer.isEditable.return_value = False
    plan.assignLayer.editingStarted = mocker.create_autospec(spec=pyqtBoundSignal)
    plan.assignLayer.editingStopped = mocker.create_autospec(spec=pyqtBoundSignal)
    plan.assignLayer.afterRollBack = mocker.create_autospec(spec=pyqtBoundSignal)
    plan.assignLayer.afterCommitChanges = mocker.create_autospec(spec=pyqtBoundSignal)
    plan.assignLayer.beforeRollBack = mocker.create_autospec(spec=pyqtBoundSignal)
    plan.assignLayer.beforeCommitChanges = mocker.create_autospec(spec=pyqtBoundSignal)
    plan.assignLayer.beforeEditingStarted = mocker.create_autospec(spec=pyqtBoundSignal)
    plan.assignLayer.allowCommitChanged = mocker.create_autospec(spec=pyqtBoundSignal)
    plan.assignLayer.selectionChanged = mocker.create_autospec(spec=pyqtBoundSignal)

    return plan
