"""QGIS Redistricting Plugin test fixtures"""
import pathlib
import shutil
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsVectorLayer
)

from redistricting.models.DistrictList import DistrictList
from redistricting.models.FieldList import FieldList
from redistricting.models.Plan import RedistrictingPlan
from redistricting.services.PlanBuilder import PlanBuilder

# pylint: disable=redefined-outer-name, unused-argument


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
    gpkg = (datadir / 'tuscaloosa_blocks.gpkg').resolve()
    layer = QgsVectorLayer(f'{gpkg}|layername=plans', 'blocks', 'ogr')
    layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4269"), False)
    QgsProject.instance().addMapLayer(layer)
    return layer


@pytest.fixture
def gpkg_path(datadir):
    return (datadir / 'tuscaloosa_plan.gpkg').resolve()


@pytest.fixture
def assign_layer(gpkg_path, qgis_new_project):
    layer = QgsVectorLayer(
        f'{gpkg_path}|layername=assignments', 'test_assignments', 'ogr')
    QgsProject.instance().addMapLayer(layer, False)
    return layer


@pytest.fixture
def dist_layer(gpkg_path, qgis_new_project):
    layer = QgsVectorLayer(
        f'{gpkg_path}|layername=districts', 'test_districts', 'ogr')
    QgsProject.instance().addMapLayer(layer, False)
    return layer


@pytest.fixture
def minimal_plan():
    plan = RedistrictingPlan('minimal', 5)
    yield plan
    plan.deleteLater()


@pytest.fixture
def valid_plan(minimal_plan: RedistrictingPlan, block_layer, gpkg_path):
    # pylint: disable=protected-access
    minimal_plan._setGeoLayer(block_layer)
    minimal_plan._geoIdField = 'geoid20'
    minimal_plan._setPopField('pop_total')
    # pylint: enable=protected-access
    minimal_plan.addLayersFromGeoPackage(gpkg_path)
    return minimal_plan


@pytest.fixture
def plan(block_layer, assign_layer, dist_layer):
    p = RedistrictingPlan.deserialize({
        'name': 'test',
        'deviation': 0.025,
        'geo-layer': block_layer.id(),
        'geo-id-field': 'geoid20',
        'dist-field': 'district',
        'pop-field': 'pop_total',
        'pop-fields': [
            {'layer': block_layer.id(),
             'field': 'vap_total',
             'expression': False,
             'caption': 'VAP'}
        ],
        'total-population': 227036,
        'assign-layer': assign_layer.id(),
        'dist-layer': dist_layer.id(),
        'num-districts': 5,
        'data-fields': [
            {'layer': block_layer.id(),
             'field': 'vap_apblack',
             'expression': False,
             'caption': 'APBVAP',
             'sum': True,
             'pctbase': 'vap_total'},
            {'layer': block_layer.id(),
             'field': 'vap_nh_white',
             'expression': False,
             'caption': 'WVAP',
             'sum': True,
             'pctbase': 'vap_total'},
            {'layer': block_layer.id(),
             'field': 'vap_hispanic',
             'expression': False,
             'caption': 'HVAP',
             'sum': True,
             'pctbase': 'vap_total'},
        ],
        'geo-fields': [
            {'layer': assign_layer.id(),
             'field': 'vtdid20',
             'expression': False,
             'caption': 'VTD'}
        ],

    }, None)

    yield p

    p.deleteLater()


@ pytest.fixture
def new_plan(block_layer, datadir: pathlib.Path, mocker: MockerFixture):
    dst = datadir / 'tuscaloosa_new_plan.gpkg'

    b = PlanBuilder()
    p: RedistrictingPlan = b \
        .setName('test') \
        .setNumDistricts(5) \
        .setDeviation(0.025) \
        .setGeoLayer(block_layer) \
        .setGeoIdField('geoid20') \
        .setDistField('district') \
        .setPopField('pop_total') \
        .appendPopField('vap_total', caption='VAP') \
        .appendDataField('vap_nh_black', caption='BVAP') \
        .appendDataField('vap_apblack', caption='APBVAP') \
        .appendDataField('vap_nh_white', caption='WVAP') \
        .appendGeoField('vtdid20', caption='VTD') \
        .createPlan(createLayers=False)
    del b

    update = mocker.patch.object(p, 'updateDistricts')
    update.return_value = None

    p.addLayersFromGeoPackage(dst)
    p.totalPopulation = 227036

    yield p

    p.deleteLater()


@pytest.fixture
def mock_plan(mocker: MockerFixture):
    plan = mocker.create_autospec(
        spec=RedistrictingPlan('mock_plan', 5, uuid4()),
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
    type(plan).geoIdField = mocker.PropertyMock(return_value='geoid20')
    type(plan).geoJoinField = mocker.PropertyMock(return_value='geoid20')
    type(plan).popJoinField = mocker.PropertyMock(return_value='geoid20')
    type(plan).popField = mocker.PropertyMock(return_value='pop_total')
    type(plan).numDistricts = mocker.PropertyMock(return_value=5)
    type(plan).numSeats = mocker.PropertyMock(return_value=5)

    districts = mocker.create_autospec(spec=DistrictList, spec_set=True, instance=True)
    type(plan).districts = mocker.PropertyMock(return_value=districts)

    pop_fields = mocker.create_autospec(spec=FieldList, spec_set=True, instance=True)
    type(plan).popFields = mocker.PropertyMock(return_value=pop_fields)

    data_fields = mocker.create_autospec(spec=FieldList, spec_set=True, instance=True)
    type(plan).dataFields = mocker.PropertyMock(return_value=data_fields)

    return plan


@pytest.fixture
def mock_taskmanager(qgis_app, mocker: MockerFixture):
    mock = mocker.patch.object(qgis_app.taskManager(), 'addTask')
    return mock
