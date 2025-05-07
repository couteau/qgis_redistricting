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

import pytest
from pytestqt.plugin import QtBot
from qgis.core import Qgis

from redistricting.models import RdsDataField, RdsGeoField, RdsPlan
from redistricting.services import PlanEditor


class TestPlanEditor:
    @pytest.fixture
    def editor(self, valid_plan):
        e = PlanEditor.fromPlan(valid_plan)
        yield e
        e.deleteLater()

    def test_update_updates_plan(self, valid_plan):
        assert valid_plan.geoIdCaption != "Test Geog"
        e = PlanEditor.fromPlan(valid_plan)
        e.setGeoDisplay("Test Geog")
        p = e.updatePlan()
        del e
        assert p is not None
        assert p.geoIdCaption == "Test Geog"

    def test_signals(self, editor: PlanEditor, valid_plan: RdsPlan, qtbot: QtBot):
        with qtbot.waitSignal(valid_plan.nameChanged):
            editor.setName("new name")
            editor.updatePlan()
        assert valid_plan.name == "new name"
        assert editor.modifiedFields == {"name"}

    def test_datafields_append_adds_field(self, editor: PlanEditor, valid_plan: RdsPlan, block_layer, qtbot: QtBot):
        with qtbot.waitSignal(valid_plan.dataFieldsChanged):
            editor.appendDataField("vap_ap_black", "APBVAP")
            editor.updatePlan()
        assert len(valid_plan.dataFields) == 1
        assert isinstance(valid_plan.dataFields[0], RdsDataField)
        assert valid_plan.dataFields[0].layer == block_layer
        assert valid_plan.dataFields[0].field == "vap_ap_black"
        assert valid_plan.dataFields[0].caption == "APBVAP"

        f1 = RdsDataField(block_layer, "pop_ap_black", caption="APBPOP")
        with qtbot.waitSignal(valid_plan.dataFieldsChanged):
            editor.appendDataField(f1)
            editor.updatePlan()
        assert len(valid_plan.dataFields) == 2
        assert isinstance(valid_plan.dataFields[1], RdsDataField)
        assert valid_plan.dataFields[1].field == "pop_ap_black"

        editor.appendDataField("vap_nh_white")
        editor.updatePlan()
        assert len(valid_plan.dataFields) == 3

    @pytest.fixture
    def bvap_field_fld(self, block_layer):
        return RdsDataField(block_layer, "vap_nh_black")

    @pytest.fixture
    def bvap_field_str(self):
        return "vap_nh_black"

    @pytest.mark.parametrize("field", ["bvap_field_str", "bvap_field_fld"])
    def test_datafields_set_error_when_duplicate_field_added(
        self,
        editor: PlanEditor,
        valid_plan: RdsPlan,
        field,
        mock_taskmanager,  # pylint: disable=unused-argument
        request,
    ):
        editor.appendDataField("vap_nh_black", "BVAP")
        editor.updatePlan()

        editor.appendDataField(request.getfixturevalue(field))
        assert editor.error() == (
            "Attempt to add duplicate field vap_nh_black to plan minimal",
            Qgis.MessageLevel.Warning,
        )
        editor.updatePlan()
        assert len(valid_plan.dataFields) == 1

    def test_datafields_throw_exception_when_invalid_field_added(self, editor: PlanEditor):
        with pytest.raises(TypeError, match="Field must be an RdsField or the name of a field"):
            editor.appendDataField(1)

    def test_datafields_throw_exception_when_non_existent_field_removed(
        self, editor: PlanEditor, bvap_field_fld: RdsDataField
    ):
        with pytest.raises(ValueError, match="Could not remove field"):
            editor.removeDataField("vap_nh_black")

        with pytest.raises(ValueError, match="Could not remove field"):
            editor.removeDataField(bvap_field_fld)

        with pytest.raises(IndexError, match="Index out of range"):
            editor.removeDataField(3)

        with pytest.raises(TypeError, match="Invalid index"):
            editor.removeDataField(3.5)

    def test_datafields_remove_field(self, editor: PlanEditor, valid_plan: RdsPlan, qtbot: QtBot):
        editor.appendDataField("pop_ap_black")
        editor.appendDataField("vap_ap_black")
        editor.appendDataField("vap_nh_white")
        editor.updatePlan()
        f1 = valid_plan.dataFields[0]

        with qtbot.waitSignal(valid_plan.dataFieldsChanged):
            editor.removeDataField("vap_ap_black")
            editor.updatePlan()
        assert len(valid_plan.dataFields) == 2
        assert valid_plan.dataFields[0].field == "pop_ap_black"
        assert valid_plan.dataFields[1].field == "vap_nh_white"

        with qtbot.waitSignal(valid_plan.dataFieldsChanged):
            editor.removeDataField(f1)
            editor.updatePlan()
        assert len(valid_plan.dataFields) == 1
        assert valid_plan.dataFields[0].field == "vap_nh_white"

        with qtbot.waitSignal(valid_plan.dataFieldsChanged):
            editor.removeDataField(0)
            editor.updatePlan()
        assert len(valid_plan.dataFields) == 0

    @pytest.fixture
    def vtd_field_fld(self, block_layer):
        return RdsGeoField(block_layer, "vtdid")

    @pytest.fixture
    def vtd_field_str(self):
        return "vtdid"

    def test_geofields_append_adds_field(
        self,
        editor: PlanEditor,
        valid_plan: RdsPlan,
        mock_taskmanager,  # pylint: disable=unused-argument
        block_layer,
        qtbot: QtBot,
    ):
        with qtbot.waitSignal(valid_plan.geoFieldsChanged):
            editor.appendGeoField("vtdid", "VTD")
            editor.updatePlan()
        assert len(valid_plan.geoFields) == 1
        assert isinstance(valid_plan.geoFields[0], RdsGeoField)
        assert valid_plan.geoFields[0].layer == block_layer
        assert valid_plan.geoFields[0].field == "vtdid"
        assert valid_plan.geoFields[0].caption == "VTD"

        f1 = RdsGeoField(block_layer, "statefp || countyfp || vtd", "VTD")
        with qtbot.waitSignal(valid_plan.geoFieldsChanged):
            editor.appendGeoField(f1)
            editor.updatePlan()
        assert len(valid_plan.geoFields) == 2
        assert valid_plan.geoFields[1].field == "statefp || countyfp || vtd"
        editor.appendGeoField("countyid")
        editor.updatePlan()
        assert len(valid_plan.geoFields) == 3

    @pytest.mark.parametrize("field", ["vtd_field_str", "vtd_field_fld"])
    def test_geofields_set_error_when_duplicate_field_added(
        self,
        editor: PlanEditor,
        valid_plan: RdsPlan,
        mock_taskmanager,  # pylint: disable=unused-argument
        field,
        request,
    ):
        editor.appendGeoField("vtdid", "VTD")
        editor.updatePlan()

        editor.appendGeoField(request.getfixturevalue(field))
        assert editor.error() == ("Attempt to add duplicate field vtdid to plan minimal", Qgis.MessageLevel.Warning)
        editor.updatePlan()
        assert len(valid_plan.geoFields) == 1

    def test_geofields_throw_exception_when_invalid_field_added(self, editor: PlanEditor):
        with pytest.raises(TypeError, match="Attempt to add invalid field"):
            editor.appendGeoField(1)

    def test_geofields_throw_exception_when_nonexistent_field_removed(self, editor: PlanEditor, vtd_field_fld):
        with pytest.raises(ValueError, match="Could not remove field"):
            editor.removeGeoField("blockid20")

        with pytest.raises(ValueError, match="Could not remove field"):
            editor.removeGeoField(vtd_field_fld)

        with pytest.raises(IndexError, match="Index out of range"):
            editor.removeGeoField(3)

        with pytest.raises(TypeError, match="Invalid index"):
            editor.removeGeoField(3.5)

    def test_geofields_remove_field(
        self,
        editor: PlanEditor,
        valid_plan: RdsPlan,
        vtd_field_fld,
        mock_taskmanager,  # pylint: disable=unused-argument
        qtbot: QtBot,
    ):
        with qtbot.waitSignal(valid_plan.geoFieldsChanged):
            editor.appendGeoField(vtd_field_fld)
            editor.appendGeoField("statefp || countyfp || vtd")
            editor.appendGeoField("countyid")
            editor.updatePlan()
        f1 = valid_plan.geoFields[1]

        with qtbot.waitSignal(valid_plan.geoFieldsChanged):
            editor.removeGeoField("vtdid")
            editor.updatePlan()
        assert len(valid_plan.geoFields) == 2
        assert valid_plan.geoFields[0].field == "statefp || countyfp || vtd"
        assert valid_plan.geoFields[1].field == "countyid"

        with qtbot.waitSignal(valid_plan.geoFieldsChanged):
            editor.removeGeoField(f1)
            editor.updatePlan()
        assert len(valid_plan.geoFields) == 1
        assert valid_plan.geoFields[0].field == "countyid"

        with qtbot.waitSignal(valid_plan.geoFieldsChanged):
            editor.removeGeoField(0)
            editor.updatePlan()
        assert len(valid_plan.geoFields) == 0
