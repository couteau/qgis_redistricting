"""QGIS Redistricting Plugin - unit tests for RdsPlan class

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
from uuid import UUID

import pytest
from pytestqt.plugin import QtBot

from redistricting.models import (
    RdsDataField,
    RdsField,
    RdsPlan
)
from redistricting.models.serialize import serialize_model

# pylint: disable=too-many-public-methods,protected-access


class TestPlan:
    @pytest.mark.parametrize('params',
                             [
                                 {'name': 'test'},
                                 {'name': None, 'numDistricts': 2},
                                 {'name': True, 'numDistricts': 2},
                                 {'name': 'test', 'numDistricts': 2.5},
                                 {'name': 'test', 'numDistricts': 2, 'id': False},
                                 {'name': 'test', 'numDistricts': 2, 'id': 'd2a95531-0de4-4556-bbe0-bb251d2f2026'}
                             ])
    def test_create_plan_throws_typeerror_with_wrong_type_params(self, params):
        with pytest.raises(TypeError):
            plan = RdsPlan(**params)  # pylint: disable=unused-variable

    @pytest.mark.parametrize('params',
                             [
                                 {'name': '', 'numDistricts': 2},
                                 {'name': 'test', 'numDistricts': 1},
                                 {'name': 'test', 'numDistricts': 2001},
                             ]
                             )
    def test_create_plan_throws_typeerror_with_invalid_params(self, params):
        with pytest.raises(ValueError):
            plan = RdsPlan(**params)  # pylint: disable=unused-variable

    @pytest.mark.parametrize('params,expected',
                             [
                                 [{'name': 'test', 'numDistricts': 5},  ['test', 5, None]],
                                 [
                                     {'name': 'test', 'numDistricts': 2, 'id': UUID(
                                         'd2a95531-0de4-4556-bbe0-bb251d2f2026')},
                                     ['test', 2, 'd2a95531-0de4-4556-bbe0-bb251d2f2026']
                                 ],
                             ])
    def test_create_plan_with_valid_params(self, params, expected):
        plan = RdsPlan(**params)
        assert plan.name == expected[0]
        assert plan.numDistricts == expected[1]
        assert isinstance(plan.id, UUID)
        if expected[2]:
            assert str(plan.id) == expected[2]

    def test_repr(self, plan):
        s = repr(plan)
        assert s

    def test_create_plan_sets_expected_defaults(self):
        plan = RdsPlan('test', 5)
        assert plan.name == 'test'
        assert plan.numSeats == 5
        assert plan.assignLayer is None
        assert plan.distLayer is None
        assert plan.popLayer is None
        assert plan.popJoinField is None
        assert plan.geoLayer is None
        assert plan.geoJoinField is None
        assert plan.distField == 'district'
        assert plan.geoIdField is None
        assert plan.popField is None
        assert len(plan.popFields) == 0
        assert plan.geoIdCaption is None
        assert plan.deviation == 0
        assert plan.totalPopulation == 0
        assert len(plan.geoFields) == 0
        assert len(plan.dataFields) == 0
        assert len(plan.districts) == 1
        assert plan.districts[0].name == 'Unassigned'  # pylint: disable=unsubscriptable-object

    def test_new_plan_is_not_valid(self):
        plan = RdsPlan('test', 5)
        assert not plan.isValid()

    def test_assign_name_updates_layer_names(self, gpkg_path, qtbot: QtBot):
        plan = RdsPlan('oldname', 45)
        plan.addLayersFromGeoPackage(gpkg_path)
        try:
            assert plan.distLayer.name() == 'oldname_districts'
            assert plan.assignLayer.name() == 'oldname_assignments'
            with qtbot.wait_signal(plan.nameChanged):
                plan.name = 'newname'
            assert plan.distLayer.name() == 'newname_districts'
            assert plan.assignLayer.name() == 'newname_assignments'
        finally:
            plan._setAssignLayer(None)
            plan._setDistLayer(None)

    def test_datafields_assign(self, valid_plan: RdsPlan, block_layer, qtbot: QtBot):
        with qtbot.waitSignal(valid_plan.dataFieldsChanged):
            valid_plan.dataFields = [RdsDataField(block_layer, 'vap_nh_black')]

        assert len(valid_plan.dataFields) == 1

    # pylint: disable-next=unused-argument
    def test_geofields_assign(self, valid_plan: RdsPlan, block_layer, mock_taskmanager, qtbot: QtBot):
        with qtbot.waitSignal(valid_plan.geoFieldsChanged):
            valid_plan.geoFields = [RdsField(block_layer, 'vtdid20')]
        assert len(valid_plan.geoFields) == 1
        assert len(valid_plan.stats.splits) == 1

    def test_addgeopackage_sets_error_package_doesnt_exist(self, datadir):
        plan = RdsPlan('test', 5)
        gpkg = datadir / 'dummy.gpkg'
        with pytest.raises(ValueError, match=f'File {gpkg} does not exist'):
            plan.addLayersFromGeoPackage(gpkg)

    def test_addgeopackage_adds_layers_to_project_when_valid_gpkg(self, datadir):
        plan = RdsPlan('test', 5)
        gpkg = datadir / 'tuscaloosa_plan.gpkg'
        plan.addLayersFromGeoPackage(gpkg)
        assert plan.assignLayer.name() == 'test_assignments'
        assert plan.distLayer.name() == 'test_districts'
        assert plan.geoIdField == 'geoid'
        plan._setAssignLayer(None)
        plan._setDistLayer(None)

    def test_serialize(self, plan: RdsPlan, block_layer, assign_layer, dist_layer):
        data = serialize_model(plan)
        assert data == {
            'id': str(plan.id),
            'name': 'test',
            'description': '',
            'num-districts': 5,
            'num-seats': 5,
            'deviation': 0.025,
            'geo-layer': block_layer.id(),
            'geo-join-field': 'geoid20',
            'pop-layer': block_layer.id(),
            'pop-join-field': 'geoid20',
            'pop-field': 'pop_total',
            'pop-fields': {
                'vap_total': {'layer': block_layer.id(),
                              'field': 'vap_total',
                              'caption': 'VAP'}
            },
            'assign-layer': assign_layer.id(),
            'geo-id-field': 'geoid20',
            'geo-id-caption': 'geoid20',
            'dist-layer': dist_layer.id(),
            'dist-field': 'district',
            'data-fields': {
                'vap_ap_black': {'layer': block_layer.id(),
                                 'field': 'vap_ap_black',
                                 'caption': 'APBVAP',
                                 'sum-field': True,
                                 'pct-base': 'vap_total'},
                'vap_nh_white': {'layer': block_layer.id(),
                                 'field': 'vap_nh_white',
                                 'caption': 'WVAP',
                                 'sum-field': True,
                                 'pct-base': 'vap_total'},
                'vap_hispanic': {'layer': block_layer.id(),
                                 'field': 'vap_hispanic',
                                 'caption': 'HVAP',
                                 'sum-field': True,
                                 'pct-base': 'vap_total'},
            },
            'geo-fields': {
                'vtdid20': {'layer': assign_layer.id(),
                            'field': 'vtdid20',
                            'caption': 'VTD'}
            },
            'stats': {'total-population': 227036, 'splits': {'vtdid20': {'field': 'vtdid20', 'data': []}}}
        }
