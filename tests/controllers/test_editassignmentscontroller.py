from redistricting import (
    controllers,
    gui,
    services
)


class TestEditAssignmentsController:
    def test_edit_signals(self, controller: controllers.EditAssignmentsController, qtbot):
        plan = controller.activePlan
        with qtbot.wait_signal(plan.assignLayer.editingStarted):
            plan.assignLayer.startEditing()
        assert controller.actionCommitPlanChanges.isEnabled()
        assert controller.actionRollbackPlanChanges.isEnabled()
        with qtbot.wait_signal(plan.assignLayer.editingStopped):
            plan.assignLayer.rollBack(True)
        assert not controller.actionCommitPlanChanges.isEnabled()
        assert not controller.actionRollbackPlanChanges.isEnabled()
