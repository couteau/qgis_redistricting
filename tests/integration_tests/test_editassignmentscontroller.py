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
