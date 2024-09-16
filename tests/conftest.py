"""QGIS Redistricting Plugin test fixtures"""
import pathlib
import shutil

import pytest
from pytest_mock import MockerFixture
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsVectorLayer
)

# pylint: disable=redefined-outer-name, unused-argument, protected-access


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config):
    from .plan_fixtures import \
        PlanFixtures  # pylint: disable=import-outside-toplevel
    config.pluginmanager.register(PlanFixtures())


@pytest.fixture(autouse=True)
def patch_iface(qgis_iface,  mocker: MockerFixture):
    qgis_iface.addCustomActionForLayerType = mocker.MagicMock()
    qgis_iface.removeCustomActionForLayerType = mocker.MagicMock()
    qgis_iface.addCustomActionForLayer = mocker.MagicMock()
    qgis_iface.vectorMenu = mocker.MagicMock()
    qgis_iface.addPluginToVectorMenu = mocker.MagicMock()
    qgis_iface.removeDockWidget = mocker.MagicMock()
    qgis_iface.removePluginVectorMenu = mocker.MagicMock()
    qgis_iface.layerTreeView = mocker.MagicMock()


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
