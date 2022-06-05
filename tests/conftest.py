"""QGIS Redistricting Plugin test fixtures"""

import shutil
import pathlib
import pytest
from qgis.core import QgsProject, QgsVectorLayer
from redistricting.core.Plan import RedistrictingPlan


# pylint: disable=redefined-outer-name, unused-argument


@pytest.fixture
def block_layer(qgis_new_project):
    gpkg = pathlib.Path(pathlib.Path(__file__).parent, 'tuscaloosa_blocks.gpkg').resolve()
    layer = QgsVectorLayer(f'{gpkg}|layername=plans', 'blocks', 'ogr')
    QgsProject.instance().addMapLayer(layer)
    return layer


@pytest.fixture
def gpkg_path():
    return pathlib.Path(pathlib.Path(__file__).parent, 'tuscaloosa_plan.gpkg').resolve()


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
def new_plan(gpkg_path, block_layer, tmp_path: pathlib.Path):
    dst = pathlib.Path(tmp_path, 'tuscaloosa_new_plan.gpkg').absolute()
    shutil.copy(gpkg_path, dst)

    p = RedistrictingPlan('test', 5)
    p.deviation = 0.025
    p.popLayer = block_layer
    p.geoIdField = 'geoid20'
    p.distField = 'district'
    p.popField = 'pop_total'
    p.vapField = 'vap_total'
    p.totalPopulation = 227036

    p.assignLayer = QgsVectorLayer(
        f'{dst}|layername=assignments', 'test_assignments', 'ogr')
    p.distLayer = QgsVectorLayer(
        f'{dst}|layername=districts', 'test_districts', 'ogr')

    p.appendDataField('vap_nh_black', caption='BVAP')
    p.appendDataField('vap_apblack', caption='APBVAP')
    p.appendDataField('vap_nh_white', caption='WVAP')

    p.appendGeoField('vtdid20', caption='VTD')
    return p
