"""QGIS Redistricting Plugin - test fixtures

Copyright 2022-2024, Stuart C. Naifeh

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
import contextlib
import os
import pathlib
import shutil
import tempfile
import unittest.mock
from typing import (
    TYPE_CHECKING,
    Any,
    Generator,
    Optional,
    Union,
    overload
)
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsLayerTree,
    QgsMapLayer,
    QgsProject,
    QgsRelationManager,
    QgsVectorLayer
)
from qgis.gui import (
    Qgis,
    QgisInterface,
    QgsGui,
    QgsLayerTreeView,
    QgsMapCanvas
)
from qgis.PyQt import (
    QtCore,
    QtWidgets,
    sip
)

if TYPE_CHECKING:
    from _pytest.fixtures import SubRequest

# pylint: disable=redefined-outer-name, unused-argument, protected-access


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
def block_layer(datadir: pathlib.Path, qgis_new_project):
    gpkg = (datadir / 'tuscaloosa.gpkg').resolve()
    layer = QgsVectorLayer(f'{gpkg}|layername=block20', 'blocks', 'ogr')
    layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4269"), False)
    QgsProject.instance().addMapLayer(layer)
    return layer


@pytest.fixture
def vtd_layer(datadir: pathlib.Path, qgis_new_project):
    gpkg = (datadir / 'tuscaloosa.gpkg').resolve()
    layer = QgsVectorLayer(f'{gpkg}|layername=vtd20', 'vtd', 'ogr')
    layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4269"), False)
    QgsProject.instance().addMapLayer(layer)
    return layer


@pytest.fixture
def county_layer(datadir: pathlib.Path, qgis_new_project):
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
def assign_layer(plan_gpkg_path, qgis_new_project):
    layer = QgsVectorLayer(
        f'{plan_gpkg_path}|layername=assignments', 'test_assignments', 'ogr')
    QgsProject.instance().addMapLayer(layer, False)
    return layer


@pytest.fixture
def dist_layer(plan_gpkg_path, qgis_new_project):
    layer = QgsVectorLayer(
        f'{plan_gpkg_path}|layername=districts', 'test_districts', 'ogr')
    QgsProject.instance().addMapLayer(layer, False)
    return layer


@pytest.fixture
def mock_taskmanager(qgis_app, mocker: MockerFixture):
    mock = mocker.patch.object(qgis_app.taskManager(), 'addTask')
    return mock


try:
    _QGIS_VERSION = Qgis.versionInt()
except AttributeError:
    _QGIS_VERSION = Qgis.QGIS_VERSION_INT

_APP: Optional[QgsApplication] = None
_CANVAS: Optional[QgsMapCanvas] = None
_IFACE: Optional[QgisInterface] = None
_PARENT: Optional[QtWidgets.QWidget] = None
_QGIS_CONFIG_PATH: Optional[pathlib.Path] = None

CANVAS_SIZE = (600, 600)


class MockMessageBar(QtCore.QObject):
    """Mocked message bar to hold the messages."""

    def __init__(self) -> None:
        super().__init__()
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
    initializationCompleted = QtCore.pyqtSignal()
    projectRead = QtCore.pyqtSignal()
    newProjectCreated = QtCore.pyqtSignal()
    layerSavedAs = QtCore.pyqtSignal("PyQt_PyObject", str)
    currentLayerChanged = QtCore.pyqtSignal()

    def __init__(self, canvas: QgsMapCanvas, parent: QtWidgets.QMainWindow):
        super().__init__()
        self.setParent(parent)
        self._canvases = [canvas]
        self._layers: list[QgsMapLayer] = []
        self._toolbars: dict[str, QtWidgets.QToolBar] = {}
        self._layerTreeView = QgsLayerTreeView(parent)
        self._layerTreeView.currentLayerChanged.connect(self.currentLayerChanged)
        self._activeLayerId = None
        self._messageBar = MockMessageBar()
        QgsProject.instance().layersAdded.connect(self.addLayers)
        QgsProject.instance().removeAll.connect(self.removeAllLayers)

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

    @QtCore.pyqtSlot("QList<QgsMapLayer*>")
    def addLayers(self, layers: list[QgsMapLayer]) -> None:
        """Handle layers being added to the registry so they show up in canvas.

        :param layers: list<QgsMapLayer> list of map layers that were added

        .. note:: The QgsInterface api does not include this method,
            it is added here as a helper to facilitate testing.
        """
        current_layers = self._canvases[0].layers()
        final_layers = []
        for layer in current_layers:
            final_layers.append(layer)
        for layer in layers:
            final_layers.append(layer)
        self._layers = final_layers

        self._canvases[0].setLayers(final_layers)

    @QtCore.pyqtSlot()
    def removeAllLayers(self) -> None:
        """Remove layers from the canvas before they get deleted."""
        if not sip.isdeleted(self._canvases[0]):
            self._canvases[0].setLayers([])
        self._layers = []

    def newProject(self, promptToSaveFlag: bool = False) -> None:
        """Create new project."""
        # noinspection PyArgumentList
        instance = QgsProject.instance()
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

    def iconSize(self) -> QtCore.QSize:
        return QtCore.QSize(24, 24)

    def mainWindow(self) -> QtWidgets.QMainWindow:
        return self.parent()

    def addToolBar(self, toolbar: Union[str, QtWidgets.QToolBar]) -> QtWidgets.QToolBar:
        """Add toolbar with specified name.

        :param toolbar: Name for the toolbar or QToolBar object.
        """
        if isinstance(toolbar, str):
            name = toolbar
            _toolbar = QtWidgets.QToolBar(name, parent=self.parent())
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

    projectMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)

    projectImportExportMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    addProjectImportAction = unittest.mock.MagicMock()
    removeProjectImportAction = unittest.mock.MagicMock()

    editMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    viewMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    layerMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    newLayerMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    addLayerMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    settingsMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    pluginMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    pluginHelpMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    rasterMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    databaseMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    vectorMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    firstRightStandardMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    windowMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)
    helpMenu = unittest.mock.MagicMock(spec=QtWidgets.QMenu)

    fileToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    layerToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    dataSourceManagerToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    mapNavToolToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    digitizeToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    advancedDigitizeToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    shapeDigitizeToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    attributesToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    selectionToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    pluginToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    helpToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    rasterToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    vectorToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    databaseToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)
    webToolBar = unittest.mock.MagicMock(spec=QtWidgets.QToolBar)

    mapToolActionGroup = unittest.mock.MagicMock(spec=QtWidgets.QActionGroup)

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

    actionNewProject = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionOpenProject = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSaveProject = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSaveProjectAs = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSaveMapAsImage = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionProjectProperties = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionCreatePrintLayout = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionShowLayoutManager = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionExit = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionCutFeatures = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionCopyFeatures = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionPasteFeatures = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddFeature = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionDeleteSelected = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionMoveFeature = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSplitFeatures = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSplitParts = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddRing = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddPart = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSimplifyFeature = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionDeleteRing = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionDeletePart = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionVertexTool = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionVertexToolActiveLayer = unittest.mock.MagicMock(spec=QtWidgets.QAction)

    actionPan = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionPanToSelected = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionZoomIn = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionZoomOut = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSelect = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSelectRectangle = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSelectPolygon = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSelectFreehand = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSelectRadius = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionIdentify = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionFeatureAction = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionMeasure = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionMeasureArea = unittest.mock.MagicMock(spec=QtWidgets.QAction)

    actionZoomFullExtent = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionZoomToLayers = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionZoomToSelected = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionZoomLast = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionZoomNext = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionZoomActualSize = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionMapTips = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionNewBookmark = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionShowBookmarks = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionDraw = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionNewVectorLayer = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddOgrLayer = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddRasterLayer = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddPgLayer = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddWmsLayer = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddXyzLayer = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddVectorTileLayer = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddPointCloudLayer = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddAfsLayer = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddAmsLayer = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionCopyLayerStyle = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionPasteLayerStyle = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionOpenTable = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionOpenFieldCalculator = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionOpenStatisticalSummary = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionToggleEditing = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSaveActiveLayerEdits = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAllEdits = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSaveEdits = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionSaveAllEdits = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionRollbackEdits = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionRollbackAllEdits = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionCancelEdits = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionCancelAllEdits = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionLayerSaveAs = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionDuplicateLayer = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionLayerProperties = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddToOverview = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAddAllToOverview = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionRemoveAllFromOverview = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionHideAllLayers = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionShowAllLayers = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionHideSelectedLayers = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionToggleSelectedLayers = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionToggleSelectedLayersIndependently = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionHideDeselectedLayers = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionShowSelectedLayers = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionManagePlugins = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionPluginListSeparator = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionShowPythonDialog = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionToggleFullScreen = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionOptions = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionCustomProjection = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionHelpContents = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionQgisHomePage = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionCheckQgisVersion = unittest.mock.MagicMock(spec=QtWidgets.QAction)
    actionAbout = unittest.mock.MagicMock(spec=QtWidgets.QAction)


def _start_and_configure_qgis_app():
    global _APP, _CANVAS, _IFACE, _PARENT, _QGIS_CONFIG_PATH  # noqa: PLW0603 # pylint: disable=global-statement

    # Use temporary path for QGIS config
    _QGIS_CONFIG_PATH = pathlib.Path(tempfile.mkdtemp(prefix="pytest-qgis"))
    os.environ["QGIS_CUSTOM_CONFIG_PATH"] = str(_QGIS_CONFIG_PATH)

    _APP = QgsApplication([], GUIenabled=True)
    _APP.initQgis()
    QgsGui.editorWidgetRegistry().initEditors()
    QgsProject.instance().legendLayersAdded.connect(_APP.processEvents)

    _PARENT = QtWidgets.QMainWindow()
    _CANVAS = QgsMapCanvas(_PARENT)
    _PARENT.resize(QtCore.QSize(CANVAS_SIZE[0], CANVAS_SIZE[1]))
    _CANVAS.resize(QtCore.QSize(CANVAS_SIZE[0], CANVAS_SIZE[1]))

    # QgisInterface is a stub implementation of the QGIS plugin interface
    _IFACE = MockQgisInterface(_CANVAS, _PARENT)

    if _QGIS_VERSION >= 31800:
        from qgis.utils import \
            iface  # noqa: F401 # pylint: disable=unused-import, import-outside-toplevel # This import is required

        unittest.mock.patch("qgis.utils.iface", _IFACE).start()

    if _APP is not None:
        # QGIS zooms to the layer's extent if it
        # is the first layer added to the map.
        # If the qgis_show_map marker is used, this zooming might occur
        # at some later time when events are processed (e.g. at qtbot.wait call)
        # and this might change the extent unexpectedly.
        # It is better to process events right after adding the
        # layer to avoid these kind of problems.
        QgsProject.instance().legendLayersAdded.connect(_APP.processEvents)


_start_and_configure_qgis_app()


@pytest.fixture(autouse=True, scope="session")
def qgis_app(request: "SubRequest") -> Generator[QgsApplication, Any, Any]:
    yield _APP

    assert _APP
    QgsProject.instance().legendLayersAdded.disconnect(_APP.processEvents)
    if not sip.isdeleted(_CANVAS) and _CANVAS is not None:
        _CANVAS.deleteLater()
    _APP.exitQgis()
    if _QGIS_CONFIG_PATH and _QGIS_CONFIG_PATH.exists():
        with contextlib.suppress(PermissionError):
            shutil.rmtree(_QGIS_CONFIG_PATH)


@pytest.fixture(scope="session")
def qgis_parent(qgis_app: QgsApplication) -> QtWidgets.QWidget:  # noqa: ARG001
    return _PARENT


@pytest.fixture(scope="session")
def qgis_canvas() -> QgsMapCanvas:
    assert _CANVAS
    return _CANVAS


@pytest.fixture(scope="session")
def qgis_iface() -> QgisInterface:
    assert _IFACE
    return _IFACE


@pytest.fixture
def qgis_new_project(qgis_iface: QgisInterface) -> None:
    """
    Initializes new QGIS project by removing layers and relations etc.
    """
    qgis_iface.newProject()


# pylint: disable=wrong-import-position
from redistricting.services.planbuilder import PlanBuilder  # isort:skip # nopep8
from redistricting.services.districtio import DistrictReader  # isort:skip # nopep8
from redistricting.models.plan import RdsPlan  # isort: skip # nopep8
from redistricting.models.base.serialization import deserialize  # isort: skip # nopep8


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
        'total-population': 227036,
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
    p.updateMetrics(227036, None, None)

    yield p

    p._setAssignLayer(None)
    p._setDistLayer(None)
    p.deleteLater()


@pytest.fixture
def mock_plan(mocker: MockerFixture) -> RdsPlan:
    mocker.patch('redistricting.models.plan.pyqtSignal', spec=QtCore.pyqtBoundSignal)
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
    plan.assignLayer.editingStarted = mocker.create_autospec(spec=QtCore.pyqtBoundSignal)
    plan.assignLayer.editingStopped = mocker.create_autospec(spec=QtCore.pyqtBoundSignal)
    plan.assignLayer.afterRollBack = mocker.create_autospec(spec=QtCore.pyqtBoundSignal)
    plan.assignLayer.afterCommitChanges = mocker.create_autospec(spec=QtCore.pyqtBoundSignal)
    plan.assignLayer.beforeRollBack = mocker.create_autospec(spec=QtCore.pyqtBoundSignal)
    plan.assignLayer.beforeCommitChanges = mocker.create_autospec(spec=QtCore.pyqtBoundSignal)
    plan.assignLayer.beforeEditingStarted = mocker.create_autospec(spec=QtCore.pyqtBoundSignal)
    plan.assignLayer.allowCommitChanged = mocker.create_autospec(spec=QtCore.pyqtBoundSignal)
    plan.assignLayer.selectionChanged = mocker.create_autospec(spec=QtCore.pyqtBoundSignal)

    return plan
