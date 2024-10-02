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
import pytest
from pytestqt.qtbot import QtBot
from qgis.core import QgsProject

from redistricting import (
    controllers,
    models,
    services
)


class TestPlanEditController:
    @pytest.fixture
    def controller(self, qgis_iface, planmanager, toolbar, assignment_service):
        controller = controllers.EditAssignmentsController(
            qgis_iface, QgsProject.instance(), planmanager,
            toolbar, assignment_service
        )
        controller.load()
        return controller

    def test_edit_signals(self, controller: controllers.EditAssignmentsController, planmanager: services.PlanManager, qtbot: QtBot, plan: models.RdsPlan):
        planmanager.appendPlan(plan)
        with qtbot.wait_signal(plan.assignLayer.editingStarted):
            plan.assignLayer.startEditing()
        assert controller.actionCommitPlanChanges.isEnabled()
        assert controller.actionRollbackPlanChanges.isEnabled()
        with qtbot.wait_signal(plan.assignLayer.editingStopped):
            plan.assignLayer.rollBack(True)
        assert not controller.actionCommitPlanChanges.isEnabled()
        assert not controller.actionRollbackPlanChanges.isEnabled()
