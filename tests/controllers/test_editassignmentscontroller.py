import pytest
from pytest_mock import MockerFixture

from redistricting import (
    controllers,
    gui,
    services
)


class TestEditAssignmentsController:
    @pytest.fixture
    def mock_dockwidget(self, mocker: MockerFixture):
        widget = mocker.patch('redistricting.controllers.EditCtlr.DockRedistrictingToolbox',
                              spec=gui.DockRedistrictingToolbox)
        return widget

    @pytest.fixture
    def mock_copy_dlt(self, mocker: MockerFixture):
        dlg = mocker.patch('redistricting.controllers.EditCtlr.DlgCopyPlan', spec=gui.DlgCopyPlan)
        return dlg

    @pytest.fixture
    def mock_newdistrict_dlg(self, mocker: MockerFixture):
        dlg = mocker.patch('redistricting.controllers.EditCtlr.DlgNewDistrict', spec=gui.DlgNewDistrict)
        return dlg

    @pytest.fixture
    def mock_assignment_editor(self, mocker: MockerFixture):
        assignmentEditor = mocker.create_autospec(spec=services.PlanAssignmentEditor)
        return assignmentEditor

    @pytest.fixture
    def controller(self, qgis_iface, planmanager, mock_project, mock_toolbar, mock_assignment_editor):

        controller = controllers.EditAssignmentsController(
            qgis_iface, mock_project, planmanager,
            mock_toolbar, mock_assignment_editor
        )
        controller.load()
        return controller

    def test_create_controller(self, qgis_iface, planmanager, mock_project, mock_toolbar, mock_assignment_editor):
        controller = controllers.EditAssignmentsController(
            qgis_iface, mock_project, planmanager,
            mock_toolbar, mock_assignment_editor
        )
        assert controller.actionStartPaintDistricts is not None

    def test_load(self, qgis_iface, planmanager, mock_project, mock_toolbar, mock_assignment_editor):
        controller = controllers.EditAssignmentsController(
            qgis_iface, mock_project, planmanager,
            mock_toolbar, mock_assignment_editor
        )
        assert controller.actionToggle is None
        assert controller.dockwidget is None
        controller.load()
        assert controller.actionToggle is not None
        assert controller.dockwidget is not None
