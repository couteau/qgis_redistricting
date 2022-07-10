"""QGIS Redistricting Plugin test fixtures"""

import shutil
import pathlib
import pytest
from pytest_mock.plugin import MockerFixture
from qgis.core import QgsProject, QgsVectorLayer
from redistricting.core.Plan import RedistrictingPlan
from redistricting.core.DistrictList import DistrictList
from redistricting.core.FieldList import FieldList


# pylint: disable=redefined-outer-name, unused-argument

@pytest.fixture
def datadir(tmp_path: pathlib.Path):
    d = tmp_path / 'data'
    s = pathlib.Path(__file__).parent / 'data'
    shutil.copytree(s, d)
    yield d
    shutil.rmtree(tmp_path)


@pytest.fixture
def block_layer(datadir, qgis_new_project):
    gpkg = (datadir / 'tuscaloosa_blocks.gpkg').resolve()
    layer = QgsVectorLayer(f'{gpkg}|layername=plans', 'blocks', 'ogr')
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
def plan_with_pop_layer(block_layer):
    p = RedistrictingPlan('minimal', 5)
    p.popLayer = block_layer
    return p


@pytest.fixture
def plan(block_layer, assign_layer, dist_layer):
    p = RedistrictingPlan.deserialize({
        'name': 'test',
        'deviation': 0.025,
        'pop-layer': block_layer.id(),
        'geo-id-field': 'geoid20',
        'dist-field': 'district',
        'pop-field': 'pop_total',
        'vap-field': 'vap_total',
        'total-population': 227036,
        'assign-layer': assign_layer.id(),
        'dist-layer': dist_layer.id(),
        'num-districts': 5,
        'districts': [
            {'district': 1, 'name': 'Council District 1', 'members': 1},
            {'district': 2, 'name': 'Council District 2', 'members': 1},
        ],
        'data-fields': [
            {'layer': block_layer.id(),
             'field': 'vap_nh_black',
             'expression': False,
             'caption': 'BVAP',
             'sum': True,
             'pctvap': True},
            {'layer': block_layer.id(),
             'field': 'vap_apblack',
             'expression': False,
             'caption': 'APBVAP',
             'sum': True,
             'pctvap': True},
            {'layer': block_layer.id(),
             'field': 'vap_nh_white',
             'expression': False,
             'caption': 'WVAP',
             'sum': True,
             'pctvap': True},
        ],
        'geo-fields': [
            {'layer': assign_layer.id(),
             'field': 'vtdid20',
             'expression': False,
             'caption': 'VTD'}
        ],

    }, None)

    return p


@ pytest.fixture
def new_plan(gpkg_path, block_layer, datadir: pathlib.Path, mocker: MockerFixture):
    dst = pathlib.Path(datadir, 'tuscaloosa_new_plan.gpkg').absolute()
    shutil.copy(gpkg_path, dst)

    p = RedistrictingPlan('test', 5)
    update = mocker.patch.object(p.districts, 'updateDistricts')
    update.return_value = None

    p.deviation = 0.025
    p.popLayer = block_layer
    p.geoIdField = 'geoid20'
    p.distField = 'district'
    p.popField = 'pop_total'
    p.vapField = 'vap_total'
    p.totalPopulation = 227036

    p.addLayersFromGeoPackage(dst)

    p.appendDataField('vap_nh_black', caption='BVAP')
    p.appendDataField('vap_apblack', caption='APBVAP')
    p.appendDataField('vap_nh_white', caption='WVAP')

    p.appendGeoField('vtdid20', caption='VTD')
    return p


@pytest.fixture
def mock_plan(mocker: MockerFixture, assign_layer, dist_layer, block_layer):
    plan = mocker.create_autospec(
        spec=RedistrictingPlan,
        spec_set=True,
        instance=True
    )
    type(plan).assignLayer = mocker.PropertyMock(return_value=assign_layer)
    type(plan).distLayer = mocker.PropertyMock(return_value=dist_layer)
    type(plan).popLayer = mocker.PropertyMock(return_value=block_layer)
    type(plan).sourceLayer = mocker.PropertyMock(return_value=block_layer)
    type(plan).distField = mocker.PropertyMock(return_value='district')
    type(plan).geoIdField = mocker.PropertyMock(return_value='geoid20')
    type(plan).sourceIdField = mocker.PropertyMock(return_value='geoid20')
    type(plan).joinField = mocker.PropertyMock(return_value='geoid20')
    type(plan).popField = mocker.PropertyMock(return_value='pop_total')
    type(plan).vapField = mocker.PropertyMock(return_value='vap_total')
    type(plan).cvapField = mocker.PropertyMock(return_value=None)
    type(plan).numDistricts = mocker.PropertyMock(return_value=5)

    districts = mocker.create_autospec(spec=DistrictList, spec_set=True, instance=True)
    type(plan).districts = mocker.PropertyMock(return_value=districts)

    data_fields = mocker.create_autospec(spec=FieldList, spec_set=True, instance=True)
    type(plan).dataFields = mocker.PropertyMock(return_value=data_fields)

    return plan
