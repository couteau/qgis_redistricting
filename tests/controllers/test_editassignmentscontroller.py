import pytest
from pytest_mock import MockerFixture
from qgis.gui import QgsFieldComboBox
from qgis.PyQt.QtWidgets import QAction

from redistricting import (
    controllers,
    gui,
    services
)

# pylint: disable=unused-argument


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
    def patch_districttools_dockwidget(self, mocker: MockerFixture):
        mocker.patch('redistricting.gui.DistrictTools.QgsFieldModel')

        registry = mocker.patch('redistricting.controllers.BaseCtlr.ActionRegistry')
        mocker.patch.object(registry.return_value, 'createAction', new=lambda *args, **kwargs: QAction())
        # registry.return_value.createAction.return_value = QAction()
        registry.return_value.actionSaveAsNew = QAction()

        registry = mocker.patch('redistricting.gui.DistrictTools.ActionRegistry')
        registry.return_value.actionCreateDistrict = QAction()
        registry.return_value.actionEditTargetDistrict = QAction()
        registry.return_value.actionEditSourceDistrict = QAction()
        mocker.patch.object(registry.return_value, 'createAction', new=lambda *args, **kwargs: QAction())

        return registry

    @pytest.fixture
    def controller(self, qgis_iface, planmanager, mock_project, mock_toolbar, mock_assignment_editor, patch_districttools_dockwidget):
        controller = controllers.EditAssignmentsController(
            qgis_iface, mock_project, planmanager,
            mock_toolbar, mock_assignment_editor
        )
        controller.load()
        return controller

    def test_create_controller(self, qgis_iface, planmanager, mock_project, mock_toolbar, mock_assignment_editor, mocker: MockerFixture):
        mocker.patch('redistricting.controllers.BaseCtlr.ActionRegistry')
        controller = controllers.EditAssignmentsController(
            qgis_iface, mock_project, planmanager,
            mock_toolbar, mock_assignment_editor
        )
        assert controller.actionStartPaintDistricts is not None

    def test_load(self, qgis_iface, planmanager, mock_project, mock_toolbar, mock_assignment_editor, patch_districttools_dockwidget, mocker: MockerFixture):
        controller = controllers.EditAssignmentsController(
            qgis_iface, mock_project, planmanager,
            mock_toolbar, mock_assignment_editor
        )
        assert controller.actionToggle is None
        assert controller.dockwidget is None
        controller.load()
        assert controller.actionToggle is not None
        assert controller.dockwidget is not None

    def test_unload(self, controller: controllers.EditAssignmentsController):
        controller.unload()
        assert controller.dockwidget is None

    def test_activeplanchanged(self, controller: controllers.EditAssignmentsController, mock_plan, mocker: MockerFixture):
        controller.dockwidget.cmbGeoSelect = mocker.create_autospec(QgsFieldComboBox, instance=True)
        controller.activePlanChanged(mock_plan)
        assert controller.actionStartPaintDistricts.isEnabled()
        assert not controller.actionCreateDistrict.isEnabled()
        assert not controller.actionCommitPlanChanges.isEnabled()

    def test_activeplanchanged_editablelayer_enables_commit(self, controller: controllers.EditAssignmentsController, mock_plan, mocker: MockerFixture):
        mock_plan.assignLayer.isEditable.return_value = True
        controller.dockwidget.cmbGeoSelect = mocker.create_autospec(QgsFieldComboBox, instance=True)
        controller.activePlanChanged(mock_plan)
        assert controller.actionCommitPlanChanges.isEnabled()

    def test_activeplanchanged_none(self, controller: controllers.EditAssignmentsController, mock_plan, mocker: MockerFixture):
        controller.dockwidget.cmbGeoSelect = mocker.create_autospec(QgsFieldComboBox, instance=True)
        controller.activePlanChanged(mock_plan)
        assert controller.actionStartPaintDistricts.isEnabled()
        assert not controller.actionCreateDistrict.isEnabled()
        controller.activePlanChanged(None)
        assert not controller.actionStartPaintDistricts.isEnabled()

    def test_connectplansignals(self, controller: controllers.EditAssignmentsController, mock_plan, mocker: MockerFixture):
        controller.connectPlanSignals(mock_plan)
        mock_plan.assignLayer.editingStarted.connect.assert_called_once()
