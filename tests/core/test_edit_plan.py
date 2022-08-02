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
from typing import Tuple
import pytest
from pytest_mock import MockerFixture
from unittest.mock import MagicMock
from pytestqt.plugin import QtBot
from qgis.core import Qgis
from redistricting.core import PlanEditor, RedistrictingPlan, DataField, Field, RdsException
from redistricting.core.PlanEdit import QgsApplication


class TestPlanEditor:
    @pytest.fixture
    def editor(self, valid_plan):
        return PlanEditor.fromPlan(valid_plan)

    def test_update_updates_plan(self, minimal_plan, block_layer, gpkg_path):
        minimal_plan.addLayersFromGeoPackage(gpkg_path)
        e = PlanEditor.fromPlan(minimal_plan)
        e.setPopLayer(block_layer)
        e.setGeoIdField('geoid20')
        e.setPopField('pop_total')
        p = e.updatePlan()
        assert p.popLayer == block_layer

    def test_signals(self, editor: PlanEditor, valid_plan, qtbot: QtBot):
        with qtbot.waitSignal(valid_plan.planChanged,
                              check_params_cb=lambda p, f, n, o:
                              p == valid_plan and f == 'name' and n == 'new name' and o == 'minimal'
                              ):
            editor.setName('new name')
            editor.updatePlan()
        assert valid_plan.name == 'new name'

        with qtbot.waitSignals([valid_plan.dataFieldAdded, valid_plan.planChanged]):
            editor.appendDataField('vap_nh_black')
            editor.updatePlan()
        assert len(valid_plan.dataFields) == 1

        with qtbot.waitSignals([valid_plan.dataFieldRemoved, valid_plan.planChanged]):
            editor.removeDataField('vap_nh_black')
            editor.updatePlan()
        assert len(valid_plan.dataFields) == 0

        with qtbot.waitSignals([valid_plan.geoFieldAdded, valid_plan.planChanged]):
            editor.appendGeoField('vtdid20')
            editor.updatePlan()
        assert len(valid_plan.geoFields) == 1

        with qtbot.waitSignals([valid_plan.geoFieldRemoved, valid_plan.planChanged]):
            editor.removeGeoField(0)
            editor.updatePlan()
        assert len(valid_plan.geoFields) == 0

    def test_datafields_append_sets_parent(self, editor: PlanEditor, valid_plan: RedistrictingPlan):
        editor.appendDataField('vap_apblack', False, 'APBVAP')
        editor.updatePlan()
        assert valid_plan.dataFields[0].parent() is valid_plan.dataFields

    def test_datafields_append_adds_field(
        self,
        editor: PlanEditor,
        valid_plan: RedistrictingPlan,
        block_layer,
        qtbot: QtBot
    ):
        with qtbot.waitSignal(valid_plan.dataFieldAdded):
            editor.appendDataField('vap_apblack', False, 'APBVAP')
            editor.updatePlan()
        assert len(valid_plan.dataFields) == 1
        assert isinstance(valid_plan.dataFields[0], DataField)
        assert valid_plan.dataFields[0].parent() is valid_plan.dataFields
        assert valid_plan.dataFields[0].layer == block_layer
        assert valid_plan.dataFields[0].field == 'vap_apblack'
        assert not valid_plan.dataFields[0].isExpression
        assert valid_plan.dataFields[0].caption == 'APBVAP'

        f1 = DataField(block_layer, 'pop_apblack', False, caption='APBPOP')
        with qtbot.waitSignal(valid_plan.dataFieldAdded):
            editor.appendDataField(f1)
            editor.updatePlan()
        assert len(valid_plan.dataFields) == 2
        assert isinstance(valid_plan.dataFields[1], DataField)
        assert valid_plan.dataFields[1].parent() is valid_plan.dataFields
        assert valid_plan.dataFields[1].field == 'pop_apblack'

        editor.appendDataField('vap_nh_white')
        editor.updatePlan()
        assert len(valid_plan.dataFields) == 3

    @pytest.fixture
    def bvap_field_fld(self, block_layer):
        return DataField(block_layer, 'vap_nh_black', False)

    @pytest.fixture
    def bvap_field_str(self):
        return'vap_nh_black'

    @pytest.mark.parametrize('field', ['bvap_field_str', 'bvap_field_fld'])
    def test_datafields_set_error_when_duplicate_field_added(
        self,
        editor: PlanEditor,
        valid_plan: RedistrictingPlan,
        field,
        request
    ):
        editor.appendDataField('vap_nh_black', False, 'BVAP')
        editor.updatePlan()

        editor.appendDataField(request.getfixturevalue(field))
        assert editor.error() == \
            ('Attempt to add duplicate field vap_nh_black to plan minimal', Qgis.Warning)
        editor.updatePlan()
        assert len(valid_plan.dataFields) == 1

    def test_datafields_throw_exception_when_invalid_field_added(self, editor):
        with pytest.raises(ValueError):
            editor.appendDataField(1)

    def test_datafields_throw_exception_when_bad_field_added(self, editor: PlanEditor):
        with pytest.raises(RdsException):
            editor.appendDataField('not_a_field')

    def test_datafields_throw_exception_when_non_existent_field_removed(
        self,
        editor: PlanEditor,
        bvap_field_fld
    ):
        with pytest.raises(ValueError):
            editor.removeDataField('vap_nh_black')

        with pytest.raises(ValueError):
            editor.removeDataField(bvap_field_fld)

        with pytest.raises(ValueError):
            editor.removeDataField(3)

    def test_datafields_remove_field(self, editor: PlanEditor, valid_plan: RedistrictingPlan, qtbot: QtBot):
        editor.appendDataField('pop_apblack')
        editor.appendDataField('vap_apblack')
        editor.appendDataField('vap_nh_white')
        editor.updatePlan()
        f1 = valid_plan.dataFields[0]

        with qtbot.waitSignal(valid_plan.dataFieldRemoved):
            editor.removeDataField('vap_apblack')
            editor.updatePlan()
        assert len(valid_plan.dataFields) == 2
        assert valid_plan.dataFields[0].field == 'pop_apblack'
        assert valid_plan.dataFields[1].field == 'vap_nh_white'

        with qtbot.waitSignal(valid_plan.dataFieldRemoved):
            editor.removeDataField(f1)
            editor.updatePlan()
        assert len(valid_plan.dataFields) == 1
        assert valid_plan.dataFields[0].field == 'vap_nh_white'

        with qtbot.waitSignal(valid_plan.dataFieldRemoved):
            editor.removeDataField(0)
            editor.updatePlan()
        assert len(valid_plan.dataFields) == 0

    @pytest.fixture
    def vtd_field_fld(self, block_layer):
        return Field(block_layer, 'vtdid20', False)

    @pytest.fixture
    def vtd_field_str(self):
        return'vtdid20'

    @pytest.fixture
    def mock_update_geo_field_task(self, mocker: MockerFixture):
        mock = mocker.patch('redistricting.core.PlanEdit.AddGeoFieldToAssignmentLayerTask')
        taskmgr = mocker.patch.object(QgsApplication.taskManager(), 'addTask')
        return (mock, taskmgr)

    def test_geofields_append_sets_parent(
        self,
        editor: PlanEditor,
        valid_plan: RedistrictingPlan,
        mock_update_geo_field_task: Tuple[MagicMock, MagicMock]
    ):
        editor.appendGeoField('vtdid20')
        editor.updatePlan()
        assert valid_plan.geoFields[0].parent() is valid_plan.geoFields
        mock_update_geo_field_task[0].assert_called_once()
        mock_update_geo_field_task[1].assert_called_once()

    def test_geofields_append_adds_field(
        self,
        editor: PlanEditor,
        valid_plan: RedistrictingPlan,
        mock_update_geo_field_task,  # pylint: disable=unused-argument
        block_layer,
        qtbot: QtBot
    ):
        with qtbot.waitSignal(valid_plan.geoFieldAdded):
            editor.appendGeoField('vtdid20', False, 'VTD')
            editor.updatePlan()
        assert len(valid_plan.geoFields) == 1
        assert isinstance(valid_plan.geoFields[0], Field)
        assert valid_plan.geoFields[0].parent() is valid_plan.geoFields
        assert valid_plan.geoFields[0].layer == block_layer
        assert valid_plan.geoFields[0].field == 'vtdid20'
        assert not valid_plan.geoFields[0].isExpression
        assert valid_plan.geoFields[0].caption == 'VTD'

        f1 = Field(block_layer, 'statefp20 || countyfp20 || vtd', True, caption='VTD')
        with qtbot.waitSignal(valid_plan.geoFieldAdded):
            editor.appendGeoField(f1)
            editor.updatePlan()
        assert len(valid_plan.geoFields) == 2
        assert valid_plan.geoFields[1].parent() is valid_plan.geoFields
        assert valid_plan.geoFields[1].field == 'statefp20 || countyfp20 || vtd'
        assert valid_plan.geoFields[1].isExpression

        editor.appendGeoField('countyid20')
        editor.updatePlan()
        assert len(valid_plan.geoFields) == 3

    @pytest.mark.parametrize('field', ['vtd_field_str', 'vtd_field_fld'])
    def test_geofields_set_error_when_duplicate_field_added(
        self,
        editor: PlanEditor,
        valid_plan: RedistrictingPlan,
        mock_update_geo_field_task,  # pylint: disable=unused-argument
        field,
        request
    ):
        editor.appendGeoField('vtdid20', False, 'VTD')
        editor.updatePlan()

        editor.appendGeoField(request.getfixturevalue(field))
        assert editor.error() == ('Attempt to add duplicate field vtdid20 to plan minimal', Qgis.Warning)
        editor.updatePlan()
        assert len(valid_plan.geoFields) == 1

    def test_geofields_throw_exception_when_invalid_field_added(
        self,
        editor: PlanEditor
    ):
        with pytest.raises(ValueError):
            editor.appendGeoField(1)

    def test_geofields_throw_exception_when_bad_field_added(self, editor: PlanEditor):
        with pytest.raises(RdsException):
            editor.appendGeoField('not_a_field')

    def test_geofields_throw_exception_when_nonexistent_field_removed(
        self,
        editor: PlanEditor,
        vtd_field_fld
    ):
        with pytest.raises(ValueError):
            editor.removeGeoField('blockid20')

        with pytest.raises(ValueError):
            editor.removeGeoField(vtd_field_fld)

        with pytest.raises(ValueError):
            editor.removeGeoField(3)

    def test_geofields_remove_field(
        self,
        editor: PlanEditor,
        valid_plan: RedistrictingPlan,
        vtd_field_fld,
        qtbot: QtBot
    ):
        editor.appendGeoField(vtd_field_fld)
        editor.appendGeoField('statefp20 || countyfp20 || vtd', True)
        editor.appendGeoField('countyid20')
        editor.updatePlan()
        f1 = valid_plan.geoFields[1]

        with qtbot.waitSignals((valid_plan.geoFieldRemoved, valid_plan.planChanged)):
            editor.removeGeoField('vtdid20')
            editor.updatePlan()
        assert len(valid_plan.geoFields) == 2
        assert valid_plan.geoFields[0].field == 'statefp20 || countyfp20 || vtd'
        assert valid_plan.geoFields[1].field == 'countyid20'

        with qtbot.waitSignal(valid_plan.geoFieldRemoved):
            editor.removeGeoField(f1)
            editor.updatePlan()
        assert len(valid_plan.geoFields) == 1
        assert valid_plan.geoFields[0].field == 'countyid20'

        with qtbot.waitSignal(valid_plan.geoFieldRemoved):
            editor.removeGeoField(0)
            editor.updatePlan()
        assert len(valid_plan.geoFields) == 0
