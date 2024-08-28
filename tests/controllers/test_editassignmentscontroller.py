import pytest
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot
from qgis.gui import (
    QgsFieldComboBox,
    QgsMapCanvas
)
from qgis.PyQt.QtWidgets import QAction

from redistricting import (
    controllers,
    gui,
    models,
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

    @pytest.fixture
    def controller_with_plan(self, controller: controllers.EditAssignmentsController, planmanager_with_active_plan):
        controller.planManager = planmanager_with_active_plan
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

    def test_target_not_set_cannot_activate(self, controller_with_plan: controllers.EditAssignmentsController, qgis_canvas: QgsMapCanvas, qtbot: QtBot):
        controller_with_plan.setGeoField('geoid')
        assert controller_with_plan.geoField == 'geoid'
        assert controller_with_plan.targetDistrict is None
        assert controller_with_plan.sourceDistrict is None
        with qtbot.assertNotEmitted(qgis_canvas.mapToolSet):
            controller_with_plan.activateMapTool(gui.PaintTool.PaintMode.PaintByGeography)

    def test_geoid_not_set_cannot_activate(self, controller_with_plan: controllers.EditAssignmentsController, qgis_canvas: QgsMapCanvas, qtbot: QtBot):
        district = models.RdsDistrict(2)
        controller_with_plan.targetDistrictChanged(district)
        assert controller_with_plan.targetDistrict == district
        assert controller_with_plan.sourceDistrict is None
        assert controller_with_plan.geoField is None
        with qtbot.assertNotEmitted(qgis_canvas.mapToolSet):
            controller_with_plan.activateMapTool(gui.PaintTool.PaintMode.PaintByGeography)

    def test_target_set_can_activate(self, controller_with_plan: controllers.EditAssignmentsController, qgis_canvas: QgsMapCanvas, qtbot: QtBot):
        district = models.RdsDistrict(2)
        controller_with_plan.targetDistrictChanged(district)
        controller_with_plan.setGeoField('geoid')
        assert controller_with_plan.targetDistrict == district
        assert controller_with_plan.mapTool.targetDistrict() == 2
        with qtbot.waitSignal(qgis_canvas.mapToolSet):
            controller_with_plan.activateMapTool(gui.PaintTool.PaintMode.PaintByGeography)

    def test_set_invalid_geofield_throws_exception(self, controller_with_plan: controllers.EditAssignmentsController, plan):
        type(controller_with_plan.planManager).activePlan = plan
        assert len(plan.geoFields) > 0
        assert controller_with_plan.planManager.activePlan == plan
        with pytest.raises(ValueError):
            controller_with_plan.setGeoField('district')

    def test_no_plan_geofields_can_set_any_geolayer_field(self, controller_with_plan: controllers.EditAssignmentsController, plan):
        type(controller_with_plan.planManager).activePlan = plan
        plan.geoFields.clear()
        assert len(plan.geoFields) == 0
        assert 'district' not in plan.geoFields
        controller_with_plan.setGeoField('tractce')
        assert controller_with_plan.geoField == 'tractce'

        with pytest.raises(ValueError):
            controller_with_plan.setGeoField('not_a_field')
