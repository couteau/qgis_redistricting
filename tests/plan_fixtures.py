"""QGIS Redistricting Plugin - fixtures that are loaded after qgis initialization

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
import pathlib
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from qgis.core import (
    QgsProject,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import pyqtBoundSignal

from redistricting.models.base.serialization import deserialize
from redistricting.models.plan import RdsPlan
from redistricting.services.districtio import DistrictReader
from redistricting.services.planbuilder import PlanBuilder

# pylint: disable=redefined-outer-name, unused-argument, protected-access


class PlanFixtures:

    @ pytest.fixture
    def minimal_plan(self):
        return RdsPlan('minimal', 5)

    @pytest.fixture
    def valid_plan(self, minimal_plan: RdsPlan, block_layer, plan_gpkg_path):
        minimal_plan.geoLayer = block_layer
        minimal_plan.geoIdField = 'geoid'
        minimal_plan.popField = 'pop_total'
        minimal_plan.addLayersFromGeoPackage(plan_gpkg_path)
        QgsProject.instance().addMapLayers([minimal_plan.distLayer, minimal_plan.assignLayer], False)
        return minimal_plan

    @pytest.fixture
    def plan(self, qgis_parent, block_layer, assign_layer, dist_layer):
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
    def new_plan(self, block_layer: QgsVectorLayer, datadir: pathlib.Path):
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
    def mock_plan(self, mocker: MockerFixture) -> RdsPlan:
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
