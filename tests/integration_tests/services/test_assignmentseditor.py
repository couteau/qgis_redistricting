"""QGIS Redistricting Plugin - integration tests

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
import pandas as pd
import pytest
from pytestqt.qtbot import QtBot

from redistricting.models import RdsPlan
from redistricting.services import (
    AssignmentsService,
    PlanAssignmentEditor
)

# pylint: disable=protected-access


class TestAssignmentsEditor:
    @pytest.fixture
    def service(self):
        svc = AssignmentsService()
        return svc

    def test_create_service(self, service):
        assert service is not None

    def test_start_editing(self, service: AssignmentsService, plan: RdsPlan, qtbot: QtBot):
        with qtbot.waitSignal(service.editingStarted):
            editor = service.startEditing(plan)
        assert editor is not None
        assert editor._plan == plan
        assert plan in service._editors
        assert service._endEditSignals.mapping(plan) is plan.assignLayer

    def test_start_editing_when_already_editing_returns_same_editor_and_does_not_emit_signal(self, service: AssignmentsService, plan: RdsPlan, qtbot: QtBot):
        with qtbot.waitSignal(service.editingStarted):
            editor = service.startEditing(plan)
        assert editor is not None
        with qtbot.assertNotEmitted(service.editingStarted):
            assert service.startEditing(plan) is editor

        with qtbot.assertNotEmitted(service.editingStarted):
            assert service.getEditor(plan) is editor

    def test_end_editing(self, service: AssignmentsService, plan: RdsPlan, qtbot: QtBot):
        with qtbot.waitSignal(service.editingStarted):
            service.startEditing(plan)

        with qtbot.waitSignal(service.editingStopped):
            service.endEditing(plan)

    def test_end_editing_when_not_editing_no_signal(self, service: AssignmentsService, plan: RdsPlan, qtbot: QtBot):
        with qtbot.assertNotEmitted(service.editingStopped):
            service.endEditing(plan)

    def test_end_editing_on_layer_triggers_signal_on_service(self, service: AssignmentsService, plan: RdsPlan, qtbot: QtBot):
        service.startEditing(plan)
        plan.assignLayer.startEditing()
        with qtbot.waitSignal(service.editingStopped):
            plan.assignLayer.rollBack(True)

        service.startEditing(plan)
        plan.assignLayer.startEditing()
        with qtbot.waitSignal(service.editingStopped):
            plan.assignLayer.commitChanges(True)

    def test_edit_assignments_triggers_signal_on_service(self, service: AssignmentsService, plan: RdsPlan, qtbot: QtBot):
        assert plan.assignLayer.getFeature(114)[2] == 5

        editor = service.startEditing(plan)

        with qtbot.waitSignals((plan.assignLayer.editingStarted, service.assignmentsChanged, plan.assignLayer.committedAttributeValuesChanges)):
            editor.assignFeaturesToDistrict([plan.assignLayer.getFeature(114)], 1)

        assert plan.assignLayer.getFeature(114)[2] == 1

    def test_create_editor(self, plan: RdsPlan):
        editor = PlanAssignmentEditor(plan)
        assert editor._distField == plan.distField
        assert editor._undoStack == plan.assignLayer.undoStack()

    def test_edit_assignments_in_existing_transaction(self, plan: RdsPlan, qtbot: QtBot):
        assert plan.assignLayer.getFeature(114)[2] == 5

        editor = PlanAssignmentEditor(plan)
        plan.assignLayer.startEditing()
        with qtbot.waitSignal(editor.assignmentsChanged):
            with qtbot.assertNotEmitted(plan.assignLayer.editingStarted):
                with qtbot.assertNotEmitted(plan.assignLayer.committedAttributeValuesChanges):
                    editor.assignFeaturesToDistrict([plan.assignLayer.getFeature(114)], 1)

        assert plan.assignLayer.getFeature(114)[2] == 1
        plan.assignLayer.rollBack(True)
        assert plan.assignLayer.getFeature(114)[2] == 5

    def test_edit_assignments_feature_generator(self, plan: RdsPlan):
        def gen():
            yield plan.assignLayer.getFeature(114)

        assert plan.assignLayer.getFeature(114)[2] == 5
        editor = PlanAssignmentEditor(plan)
        plan.assignLayer.startEditing()
        editor.assignFeaturesToDistrict(gen(), 1)
        assert plan.assignLayer.getFeature(114)[2] == 1
        plan.assignLayer.rollBack(True)

    def test_edit_assignments_int_generator(self, plan: RdsPlan):
        def gen():
            yield 114

        assert plan.assignLayer.getFeature(114)[2] == 5
        editor = PlanAssignmentEditor(plan)
        plan.assignLayer.startEditing()
        editor.assignFeaturesToDistrict(gen(), 1)
        assert plan.assignLayer.getFeature(114)[2] == 1
        plan.assignLayer.rollBack(True)

    def test_edit_assignments_pandas_index(self, plan: RdsPlan):
        assert plan.assignLayer.getFeature(114)[2] == 5
        editor = PlanAssignmentEditor(plan)
        features = pd.Index([114])
        plan.assignLayer.startEditing()
        editor.assignFeaturesToDistrict(features, 1)
        assert plan.assignLayer.getFeature(114)[2] == 1
        plan.assignLayer.rollBack(True)

    def test_edit_reassign_district(self, plan: RdsPlan):
        assert plan.assignLayer.getFeature(114)[2] == 5
        editor = PlanAssignmentEditor(plan)
        plan.assignLayer.startEditing()
        editor.reassignDistrict(5, 0)
        assert plan.assignLayer.getFeature(114)[2] == 0
        plan.assignLayer.rollBack(True)

    def test_get_dist_features(self, plan: RdsPlan):
        editor = PlanAssignmentEditor(plan)
        f = editor.getDistFeatures("placeid", "0116312")
        assert f is not None
        l = pd.DataFrame(f, columns=plan.assignLayer.fields().names())
        assert len(l) == 47
        assert len(l.groupby("district")) == 2

        f = editor.getDistFeatures("district", 5)
        assert f is not None
        l = pd.DataFrame(f, columns=plan.assignLayer.fields().names())
        assert len(l) == 1564
