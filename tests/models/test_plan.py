"""QGIS Redistricting Plugin - unit tests for RedistrictingPlan class

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
    DataField,
    Field,
    RedistrictingPlan
)

# pylint: disable=too-many-public-methods,protected-access


class TestPlan:
    @pytest.mark.parametrize('params',
                             [
                                 ['', 2],
                                 [None, 2],
                                 [True, 2],
                                 ['test', 1],
                                 ['test', 1.5],
                                 ['test', 2, False],
                                 ['test', 2, 'd2a95531-0de4-4556-bbe0-bb251d2f2026']
                             ])
    def test_create_plan_throws_valueerror_with_invalid_params(self, params):
        with pytest.raises(ValueError, match='Cannot create redistricting plan'):
            plan = RedistrictingPlan(*params)  # pylint: disable=unused-variable

    @pytest.mark.parametrize('params,expected',
                             [
                                 [['test'], ['test', 0, None]],
                                 [['test', 5],  ['test', 5, None]],
                                 [
                                     ['test', 2, UUID('d2a95531-0de4-4556-bbe0-bb251d2f2026')],
                                     ['test', 2, 'd2a95531-0de4-4556-bbe0-bb251d2f2026']
                                 ],
                             ])
    def test_create_plan_with_valid_params(self, params, expected):
        plan = RedistrictingPlan(*params)
        assert plan.name == expected[0]
        assert plan.numDistricts == expected[1]
        assert isinstance(plan.id, UUID)
        if expected[2]:
            assert str(plan.id) == expected[2]

    def test_create_plan_sets_expected_defaults(self):
        plan = RedistrictingPlan('test', 5)
        assert plan.name == 'test'
        assert plan.numSeats == 5
        assert plan._assignLayer is None
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
        assert plan.districts[0].name == 'Unassigned'

    def test_new_plan_is_not_valid(self):
        plan = RedistrictingPlan('test', 5)
        assert not plan.isValid()

    def test_assign_name_updates_layer_names(self, gpkg_path, qtbot: QtBot):
        plan = RedistrictingPlan('oldname', 45)
        plan.addLayersFromGeoPackage(gpkg_path)
        assert plan.distLayer.name() == 'oldname_districts'
        assert plan._assignLayer.name() == 'oldname_assignments'
        with qtbot.wait_signal(plan.nameChanged):
            plan._setName('newname')
        assert plan.distLayer.name() == 'newname_districts'
        assert plan._assignLayer.name() == 'newname_assignments'
        plan._setAssignLayer(None)
        plan._setDistLayer(None)

    def test_datafields_assign(self, valid_plan: RedistrictingPlan, block_layer, qtbot: QtBot):
        with qtbot.waitSignal(valid_plan.dataFieldsChanged):
            valid_plan._setDataFields(  # pylint: disable=protected-access
                [DataField(block_layer, 'vap_nh_black', False)]
            )
        assert len(valid_plan.dataFields) == 1

    # pylint: disable-next=unused-argument
    def test_geofields_assign(self, valid_plan: RedistrictingPlan, block_layer, mock_taskmanager, qtbot: QtBot):
        with qtbot.waitSignal(valid_plan.geoFieldsChanged):
            valid_plan._setGeoFields([Field(block_layer, 'vtdid20', False)])  # pylint: disable=protected-access
        assert len(valid_plan.geoFields) == 1
        assert len(valid_plan.stats.splits) == 1

    def test_addgeopackage_sets_error_package_doesnt_exist(self, datadir):
        plan = RedistrictingPlan('test', 5)
        gpkg = datadir / 'dummy.gpkg'
        with pytest.raises(ValueError, match=f'File {gpkg} does not exist'):
            plan.addLayersFromGeoPackage(gpkg)

    def test_addgeopackage_adds_layers_to_project_when_valid_gpkg(self, datadir):
        plan = RedistrictingPlan('test', 5)
        gpkg = datadir / 'tuscaloosa_plan.gpkg'
        plan.addLayersFromGeoPackage(gpkg)
        assert plan._assignLayer.name() == 'test_assignments'
        assert plan.distLayer.name() == 'test_districts'
        assert plan.geoIdField == 'geoid20'
        plan._setAssignLayer(None)
        plan._setDistLayer(None)