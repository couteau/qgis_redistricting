from redistricting.gui import DockRedistrictingToolbox

# pylint: disable=protected-access


class TestDistrictTools:
    def test_create(self, mock_plan, mocker):
        dockwidget = DockRedistrictingToolbox()
        mocker.patch.object(dockwidget, "btnUndo")
        mocker.patch.object(dockwidget, "btnRedo")
        dockwidget.plan = mock_plan
        assert dockwidget.plan is mock_plan
        assert dockwidget.lblPlanName.text() == 'test'
        assert dockwidget.cmbGeoSelect.isEnabled()

    def test_set_plan_none_clears_widget(self, mock_plan, mocker):
        dockwidget = DockRedistrictingToolbox()
        mocker.patch.object(dockwidget, "btnUndo")
        mocker.patch.object(dockwidget, "btnRedo")
        dockwidget.plan = mock_plan
        assert dockwidget.plan is mock_plan
        dockwidget.plan = None
        assert dockwidget.plan is None
        assert dockwidget._undoStack is None
        assert dockwidget.lblPlanName.text() == 'No plan selected'
        assert not dockwidget.cmbGeoSelect.isEnabled()
