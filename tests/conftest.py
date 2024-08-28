"""QGIS Redistricting Plugin test fixtures"""
import pathlib
import shutil
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import pyqtBoundSignal

from redistricting.models.base.serialize import deserialize_model
from redistricting.models.Plan import RdsPlan
from redistricting.services.DistrictIO import DistrictReader
from redistricting.services.PlanBuilder import PlanBuilder

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
def qgis_app_with_path(qgis_app: QgsApplication, datadir: pathlib.Path):
    qgis_app.setPrefixPath(str(datadir))
    QgsProject.instance().setOriginalPath(str(datadir))


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
def minimal_plan():
    plan = RdsPlan('minimal', 5)
    return plan


@pytest.fixture
def valid_plan(minimal_plan: RdsPlan, block_layer, plan_gpkg_path):
    # pylint: disable=protected-access
    minimal_plan.geoLayer = block_layer
    minimal_plan.geoIdField = 'geoid'
    minimal_plan.popField = 'pop_total'
    # pylint: enable=protected-access
    minimal_plan.addLayersFromGeoPackage(plan_gpkg_path)
    QgsProject.instance().addMapLayers([minimal_plan.distLayer, minimal_plan.assignLayer], False)
    return minimal_plan


@pytest.fixture
def plan(block_layer, assign_layer, dist_layer):
    p: RdsPlan = deserialize_model(RdsPlan, {
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
    }, None)

    r = DistrictReader(dist_layer, popField='pop_total')
    for d in r.readFromLayer():
        if d.district == 0:
            p.districts[0].update(d)
        else:
            p.districts.append(d)

    return p


@pytest.fixture
def new_plan(block_layer, datadir: pathlib.Path, mocker: MockerFixture):
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
    p.metrics.updateMetrics(227036, None, None)

    yield p

    p._setAssignLayer(None)
    p._setDistLayer(None)
    p.deleteLater()


@pytest.fixture
def mock_plan(mocker: MockerFixture):
    mocker.patch('redistricting.models.Plan.pyqtSignal', spec=pyqtBoundSignal)
    plan = mocker.create_autospec(
        spec=RdsPlan('mock_plan', 5),
        spec_set=True
    )
    type(plan).name = mocker.PropertyMock(return_value="test")
    type(plan).id = mocker.PropertyMock(return_value=uuid4())
    type(plan).description = mocker.PropertyMock(return_value="description")
    type(plan).assignLayer = mocker.PropertyMock(return_value=mocker.create_autospec(spec=QgsVectorLayer, instance=True))
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


@pytest.fixture
def mock_taskmanager(qgis_app, mocker: MockerFixture):
    mock = mocker.patch.object(qgis_app.taskManager(), 'addTask')
    return mock
