from redistricting import controllers


class TestPlanEditController:
    def test_edit_signals(self, controller: controllers.EditAssignmentsController, planmanager, qtbot):
        plan = planmanager.activePlan
        with qtbot.wait_signal(plan.assignLayer.editingStarted):
            plan.assignLayer.startEditing()
        assert controller.actionCommitPlanChanges.isEnabled()
        assert controller.actionRollbackPlanChanges.isEnabled()
        with qtbot.wait_signal(plan.assignLayer.editingStopped):
            plan.assignLayer.rollBack(True)
        assert not controller.actionCommitPlanChanges.isEnabled()
        assert not controller.actionRollbackPlanChanges.isEnabled()
