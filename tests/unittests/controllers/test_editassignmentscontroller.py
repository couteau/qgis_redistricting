import pytest
from pytest_mock import MockerFixture
from pytestqt.qtbot import QtBot
from qgis._gui import QgisInterface
from qgis.core import QgsFeature
from qgis.gui import (
    Qgis,
    QgsFieldComboBox,
    QgsMapCanvas
)
from qgis.PyQt.QtWidgets import (
    QAction,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox
)

from redistricting.controllers import EditAssignmentsController
from redistricting.gui import (
    DlgCopyPlan,
    DlgNewDistrict,
    DockRedistrictingToolbox,
    PaintTool
)
from redistricting.models import RdsDistrict
from redistricting.services import (
    AssignmentsService,
    PlanAssignmentEditor,
    PlanCopier
)

# pylint: disable=unused-argument


class MockDlgNewDistrict(DlgNewDistrict):
    sbxDistrictNo: QSpinBox = None
    inpName: QLineEdit = None
    sbxMembers: QSpinBox = None
    txtDescription: QPlainTextEdit = None
    buttonBox: QDialogButtonBox = None


class MockDlgCopyPlan(DlgCopyPlan):
    cbxCopyAssignments: QCheckBox = None


class TestEditAssignmentsController:
    @pytest.fixture
    def mock_dockwidget(self, mocker: MockerFixture):
        widget = mocker.patch('redistricting.controllers.EditCtlr.DockRedistrictingToolbox',
                              spec=DockRedistrictingToolbox)
        return widget

    @pytest.fixture
    def mock_copy_dlg(self, mocker: MockerFixture):
        dlg = mocker.patch('redistricting.controllers.EditCtlr.DlgCopyPlan', spec=MockDlgCopyPlan)
        return dlg

    @pytest.fixture
    def mock_newdistrict_dlg(self, mocker: MockerFixture):
        dlg = mocker.patch('redistricting.controllers.EditCtlr.DlgNewDistrict', spec=MockDlgNewDistrict)
        dlg.return_value.districtNumber = 1
        dlg.return_value.districtName = "District 1"
        dlg.return_value.members = 1
        dlg.return_value.description = "Central commission district"
        return dlg

    @pytest.fixture
    def mock_assignments_editor(self, mocker: MockerFixture):
        assignmentEditor = mocker.create_autospec(spec=PlanAssignmentEditor, instance=True)
        return assignmentEditor

    @pytest.fixture
    def mock_assignments_service(self, mock_assignments_editor, mocker: MockerFixture):
        assignmentService = mocker.create_autospec(spec=AssignmentsService, instance=True)
        assignmentService.getEditor.return_value = mock_assignments_editor
        assignmentService.startEditing.return_value = mock_assignments_editor
        assignmentService.isEditing.return_value = True
        return assignmentService

    @pytest.fixture
    def patch_districttools_dockwidget(self, mocker: MockerFixture):
        mocker.patch('redistricting.controllers.EditCtlr.QgsFieldModel')

        registry = mocker.patch('redistricting.controllers.BaseCtlr.ActionRegistry')
        mocker.patch.object(registry.return_value, 'createAction', new=lambda *args, **kwargs: QAction())
        # registry.return_value.createAction.return_value = QAction()
        registry.return_value.actionSaveAsNew = QAction()
        registry.return_value.actionCreateDistrict = QAction()
        registry.return_value.actionEditTargetDistrict = QAction()
        registry.return_value.actionEditSourceDistrict = QAction()

        return registry

    @pytest.fixture
    def controller(self, qgis_iface, mock_planmanager, mock_project, mock_toolbar, mock_assignments_service, patch_districttools_dockwidget):
        controller = EditAssignmentsController(
            qgis_iface, mock_project, mock_planmanager,
            mock_toolbar, mock_assignments_service
        )
        controller.load()
        return controller

    @pytest.fixture
    def controller_with_plan(self, controller: EditAssignmentsController, mock_planmanager_with_active_plan):
        controller.planManager = mock_planmanager_with_active_plan
        return controller

    def test_create_controller(self, qgis_iface, mock_planmanager, mock_project, mock_toolbar, mock_assignments_service, mocker: MockerFixture):
        mocker.patch('redistricting.controllers.BaseCtlr.ActionRegistry')
        controller = EditAssignmentsController(
            qgis_iface, mock_project, mock_planmanager,
            mock_toolbar, mock_assignments_service
        )
        assert controller.actionStartPaintDistricts is not None

    def test_load(self, qgis_iface, mock_planmanager, mock_project, mock_toolbar, mock_assignments_service, patch_districttools_dockwidget, mocker: MockerFixture):
        controller = EditAssignmentsController(
            qgis_iface, mock_project, mock_planmanager,
            mock_toolbar, mock_assignments_service
        )
        assert controller.actionToggle is None
        assert controller.dockwidget is None
        controller.load()
        assert controller.actionToggle is not None
        assert controller.dockwidget is not None

    def test_unload(self, controller: EditAssignmentsController):
        controller.unload()
        assert controller.dockwidget is None

    def test_activeplanchanged(self, controller_with_plan: EditAssignmentsController, mock_plan, mocker: MockerFixture):
        mocker.patch.object(controller_with_plan, "dockwidget", autospec=controller_with_plan.dockwidget)
        controller_with_plan.dockwidget.cmbGeoSelect = mocker.create_autospec(QgsFieldComboBox, instance=True)
        assert controller_with_plan.geoField is None
        assert not controller_with_plan.actionStartPaintDistricts.isEnabled()
        controller_with_plan.activePlanChanged(mock_plan)
        assert controller_with_plan.geoField == mock_plan.geoIdField
        assert controller_with_plan.actionStartPaintDistricts.isEnabled()
        assert not controller_with_plan.actionCreateDistrict.isEnabled()
        assert not controller_with_plan.actionCommitPlanChanges.isEnabled()

    def test_activeplanchanged_editablelayer_enables_commit(self, controller: EditAssignmentsController, mock_plan, mocker: MockerFixture):
        mocker.patch.object(controller, "dockwidget", autospec=controller.dockwidget)
        mock_plan.assignLayer.isEditable.return_value = True
        controller.dockwidget.cmbGeoSelect = mocker.create_autospec(QgsFieldComboBox, instance=True)
        controller.activePlanChanged(mock_plan)
        assert controller.actionCommitPlanChanges.isEnabled()

    def test_activeplanchanged_none(self, controller: EditAssignmentsController, mock_plan, mocker: MockerFixture):
        mocker.patch.object(controller, "dockwidget", autospec=controller.dockwidget)
        controller.dockwidget.cmbGeoSelect = mocker.create_autospec(QgsFieldComboBox, instance=True)
        controller.activePlanChanged(mock_plan)
        assert controller.actionStartPaintDistricts.isEnabled()
        assert not controller.actionCreateDistrict.isEnabled()
        controller.activePlanChanged(None)
        assert not controller.actionStartPaintDistricts.isEnabled()

    def test_connectplansignals(self, controller: EditAssignmentsController, mock_plan):
        controller.connectPlanSignals(mock_plan)
        mock_plan.assignLayer.editingStarted.connect.assert_called_once()

    def test_target_district_changed(self, controller_with_plan: EditAssignmentsController, mock_plan, mock_district, mocker: MockerFixture):
        mocker.patch.object(controller_with_plan, 'dockwidget', autospec=controller_with_plan.dockwidget)
        controller_with_plan.activePlanChanged(mock_plan)
        assert controller_with_plan.targetDistrict is None
        controller_with_plan.targetDistrictChanged(1)
        assert controller_with_plan.targetDistrict == mock_district
        controller_with_plan.targetDistrictChanged(None)
        assert controller_with_plan.targetDistrict is None

    def test_source_district_changed(self, controller_with_plan: EditAssignmentsController, mock_plan, mock_district, mocker: MockerFixture):
        mocker.patch.object(controller_with_plan, 'dockwidget', autospec=controller_with_plan.dockwidget)
        controller_with_plan.activePlanChanged(mock_plan)
        assert controller_with_plan.sourceDistrict is None
        controller_with_plan.sourceDistrictChanged(1)
        assert controller_with_plan.sourceDistrict == mock_district
        controller_with_plan.sourceDistrictChanged(None)
        assert controller_with_plan.sourceDistrict is None

    def test_set_geofield(self, controller_with_plan):
        assert controller_with_plan.geoField is None
        controller_with_plan.setGeoField('geoid')
        assert controller_with_plan.geoField == 'geoid'

    def test_set_geofield_no_active_plan_no_set(self, controller):
        assert controller.geoField is None
        controller.setGeoField('geoid')
        assert controller.geoField is None

    def test_target_not_set_cannot_activate(self, controller_with_plan: EditAssignmentsController, qgis_canvas: QgsMapCanvas, qtbot: QtBot):
        controller_with_plan.setGeoField('geoid')
        assert controller_with_plan.geoField == 'geoid'
        assert controller_with_plan.targetDistrict is None
        assert controller_with_plan.sourceDistrict is None
        with qtbot.assertNotEmitted(qgis_canvas.mapToolSet):
            controller_with_plan.activateMapTool(PaintTool.PaintMode.PaintByGeography)

    def test_geoid_not_set_geoid_not_set_cannot_activate(self, controller_with_plan: EditAssignmentsController, qgis_canvas: QgsMapCanvas, qtbot: QtBot):
        district = RdsDistrict(2)
        controller_with_plan.targetDistrict = district
        assert controller_with_plan.sourceDistrict is None
        assert controller_with_plan.geoField is None
        with qtbot.assertNotEmitted(qgis_canvas.mapToolSet):
            controller_with_plan.activateMapTool(PaintTool.PaintMode.PaintByGeography)

    def test_target_set_geoid_set_can_activate(self, controller_with_plan: EditAssignmentsController, qgis_canvas: QgsMapCanvas, qtbot: QtBot):
        district = RdsDistrict(2)
        controller_with_plan.targetDistrict = district
        controller_with_plan.setGeoField('geoid')
        assert controller_with_plan.sourceDistrict is None
        assert controller_with_plan.geoField == 'geoid'
        with qtbot.waitSignal(qgis_canvas.mapToolSet):
            controller_with_plan.activateMapTool(PaintTool.PaintMode.PaintByGeography)

    def test_activate_with_invisible_layer_sets_error_and_returns_none(self, controller_with_plan: EditAssignmentsController, qgis_canvas: QgsMapCanvas, qtbot: QtBot,  qgis_iface, mock_project):
        mock_project.layerTreeRoot.return_value.findLayer.return_value.isVisible.return_value = False
        controller_with_plan.activateMapTool(PaintTool.PaintMode.PaintByGeography)
        qtbot.assertNotEmitted(qgis_canvas.mapToolSet)
        assert "Oops!:Cannot paint districts for a plan that is not visible. Please toggle the visibility of plan test's assignment layer." in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_set_invalid_geofield_throws_exception(self, controller_with_plan: EditAssignmentsController, plan):
        type(controller_with_plan.planManager).activePlan = plan
        assert len(plan.geoFields) > 0
        assert controller_with_plan.planManager.activePlan == plan
        with pytest.raises(ValueError):
            controller_with_plan.setGeoField('district')

    def test_no_plan_geofields_can_set_any_geolayer_field(self, controller_with_plan: EditAssignmentsController, plan):
        type(controller_with_plan.planManager).activePlan = plan
        plan.geoFields.clear()
        assert len(plan.geoFields) == 0
        assert 'district' not in plan.geoFields
        controller_with_plan.setGeoField('tractce')
        assert controller_with_plan.geoField == 'tractce'

        with pytest.raises(ValueError):
            controller_with_plan.setGeoField('not_a_field')

    def test_create_district(self, controller_with_plan: EditAssignmentsController, mock_project, mock_plan, mock_district, mock_newdistrict_dlg, mocker: MockerFixture):
        mocker.patch.object(controller_with_plan, 'dockwidget')
        controller_with_plan.activePlanChanged(mock_plan)
        type(mock_plan).allocatedDistricts = mocker.PropertyMock(return_value=0)
        type(mock_plan).allocatedSeats = mocker.PropertyMock(return_value=0)
        mock_plan.districts.__len__.return_value = 1
        mock_plan.addDistrict.return_value = mock_district
        mock_newdistrict_dlg.return_value.exec.return_value = QDialog.Accepted
        d = controller_with_plan.createDistrict()
        assert d == 1
        mock_project.setDirty.assert_called_once()
        mock_plan.addDistrict.assert_called_once()

    def test_create_district_no_active_plan_logs_error_returns_none(self, controller: EditAssignmentsController, mock_newdistrict_dlg, qgis_iface: QgisInterface):
        d = controller.createDistrict()
        assert d is None
        mock_newdistrict_dlg.assert_not_called()
        assert "Oops!:Cannot create district: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_create_district_cancel_returns_none(self, controller_with_plan: EditAssignmentsController, mock_project, mock_plan, mock_newdistrict_dlg, mocker: MockerFixture):
        mocker.patch.object(controller_with_plan, 'dockwidget')
        type(mock_plan).allocatedDistricts = mocker.PropertyMock(return_value=0)
        type(mock_plan).allocatedSeats = mocker.PropertyMock(return_value=0)
        mock_plan.districts.__len__.return_value = 1
        mock_newdistrict_dlg.return_value.exec.return_value = QDialog.Rejected
        d = controller_with_plan.createDistrict()
        assert d is None
        mock_newdistrict_dlg.assert_called_once()
        mock_project.setDirty.assert_not_called()

    def test_create_district_complete_plan_returns_none(self, controller_with_plan: EditAssignmentsController, mock_project, mock_plan, mock_newdistrict_dlg, qgis_iface):
        mock_newdistrict_dlg.return_value.exec.return_value = QDialog.Accepted
        assert mock_plan.allocatedDistricts == mock_plan.numDistricts
        d = controller_with_plan.createDistrict()
        assert d is None
        mock_newdistrict_dlg.assert_not_called()
        mock_newdistrict_dlg.return_value.exec.assert_not_called()
        mock_project.setDirty.assert_not_called()
        assert "Warning:All districts have already been allocated" in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_edit_district(self, controller_with_plan: EditAssignmentsController, mock_project, mock_district, mock_newdistrict_dlg, mocker: MockerFixture):
        mocker.patch.object(controller_with_plan, 'dockwidget')
        mock_newdistrict_dlg.return_value.exec.return_value = QDialog.Accepted
        n = mocker.PropertyMock(return_value="District Name", name="name")
        type(mock_district).name = n
        assert mock_district.district == 1
        controller_with_plan.editDistrict(mock_district)
        mock_project.setDirty.assert_called_once()
        n.assert_called_with("District 1")

    def test_edit_district_unassigned_returns(self, controller_with_plan: EditAssignmentsController, mock_project, mock_district, mock_newdistrict_dlg, mocker: MockerFixture):
        mock_newdistrict_dlg.return_value.exec.return_value = QDialog.Accepted
        type(mock_district).district = mocker.PropertyMock(return_value=0)
        controller_with_plan.editDistrict(mock_district)
        mock_project.setDirty.assert_not_called()
        mock_newdistrict_dlg.assert_not_called()

    def test_edit_district_with_no_argument_and_no_source_target_returns(self, controller_with_plan: EditAssignmentsController, mock_project, mock_newdistrict_dlg, mocker: MockerFixture):
        mocker.patch.object(controller_with_plan, 'dockwidget')
        mock_newdistrict_dlg.return_value.exec.return_value = QDialog.Accepted
        controller_with_plan.editDistrict()
        mock_project.setDirty.assert_not_called()
        mock_newdistrict_dlg.assert_not_called()

    def test_edit_district_target_from_signal(self, controller_with_plan: EditAssignmentsController, mock_project, mock_district, mock_newdistrict_dlg, mocker: MockerFixture):
        mocker.patch.object(controller_with_plan, 'dockwidget')
        mock_newdistrict_dlg.return_value.exec.return_value = QDialog.Accepted
        n = mocker.PropertyMock(return_value="District Name", name="name")
        type(mock_district).name = n
        controller_with_plan.targetDistrict = mock_district
        sender = mocker.patch.object(controller_with_plan, "sender")
        sender.return_value = controller_with_plan.actionEditTargetDistrict
        controller_with_plan.editDistrict()
        mock_project.setDirty.assert_called_once()
        n.assert_called_with("District 1")

    def test_edit_district_target(self, controller_with_plan: EditAssignmentsController, mock_project, mock_district, mock_newdistrict_dlg, mocker: MockerFixture):
        mocker.patch.object(controller_with_plan, 'dockwidget')
        mock_newdistrict_dlg.return_value.exec.return_value = QDialog.Accepted
        n = mocker.PropertyMock(return_value="District Name", name="name")
        type(mock_district).name = n
        controller_with_plan.targetDistrict = mock_district
        controller_with_plan.editTargetDistrict()
        mock_project.setDirty.assert_called_once()
        n.assert_called_with("District 1")

    def test_edit_district_source_from_signal(self, controller_with_plan: EditAssignmentsController, mock_project, mock_district, mock_newdistrict_dlg, mocker: MockerFixture):
        mocker.patch.object(controller_with_plan, 'dockwidget')
        mock_newdistrict_dlg.return_value.exec.return_value = QDialog.Accepted
        n = mocker.PropertyMock(return_value="District Name", name="name")
        type(mock_district).name = n
        controller_with_plan.sourceDistrict = mock_district
        sender = mocker.patch.object(controller_with_plan, "sender")
        sender.return_value = controller_with_plan.actionEditSourceDistrict
        controller_with_plan.editDistrict()
        mock_project.setDirty.assert_called_once()
        n.assert_called_with("District 1")

    def test_edit_district_source(self, controller_with_plan: EditAssignmentsController, mock_project, mock_district, mock_newdistrict_dlg, mocker: MockerFixture):
        mocker.patch.object(controller_with_plan, 'dockwidget')
        mock_newdistrict_dlg.return_value.exec.return_value = QDialog.Accepted
        n = mocker.PropertyMock(return_value="District Name", name="name")
        type(mock_district).name = n
        controller_with_plan.sourceDistrict = mock_district
        controller_with_plan.sourceDistrict = mock_district
        controller_with_plan.editSourceDistrict()
        mock_project.setDirty.assert_called_once()
        n.assert_called_with("District 1")

    def test_save_as_new_no_active_plan_logs_error_returns(self, controller: EditAssignmentsController, mock_copy_dlg, qgis_iface: QgisInterface):
        controller.saveChangesAsNewPlan()
        mock_copy_dlg.assert_not_called()
        assert "Oops!:Cannot save changes to new plan: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_save_as_new_no_pending_changes_logs_error_returns(self, controller_with_plan: EditAssignmentsController, mock_copy_dlg, mock_plan, qgis_iface: QgisInterface):
        mock_plan.assignLayer.isEditable.return_value = False
        controller_with_plan.saveChangesAsNewPlan()
        mock_copy_dlg.assert_not_called()
        assert "Oops!:Cannot save changes to no plan: active plan has no unsaved changes." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_save_as_new(self, controller_with_plan: EditAssignmentsController, mock_copy_dlg, mock_plan, qgis_iface: QgisInterface, mocker: MockerFixture):
        copier = mocker.patch('redistricting.controllers.EditCtlr.PlanCopier', spec=PlanCopier)
        mock_plan.assignLayer.isEditable.return_value = True
        mock_copy_dlg.return_value.exec.return_value = QDialog.Accepted
        controller_with_plan.saveChangesAsNewPlan()
        mock_copy_dlg.assert_called_once()
        mock_copy_dlg.return_value.exec.assert_called_once()
        copier.assert_called_once()
        copier.return_value.copyPlan.assert_called_once()
        copier.return_value.copyBufferedAssignments.assert_called_once()

    def test_save_as_new_cancel_returns(self, controller_with_plan: EditAssignmentsController, mock_copy_dlg, mock_plan, qgis_iface: QgisInterface, mocker: MockerFixture):
        copier = mocker.patch('redistricting.controllers.EditCtlr.PlanCopier', spec=PlanCopier)
        mock_plan.assignLayer.isEditable.return_value = True
        mock_copy_dlg.return_value.exec.return_value = QDialog.Rejected
        controller_with_plan.saveChangesAsNewPlan()
        mock_copy_dlg.assert_called_once()
        mock_copy_dlg.return_value.exec.assert_called_once()
        copier.assert_not_called()

    def test_start_painting(self, controller_with_plan: EditAssignmentsController, mock_assignments_service: AssignmentsService):
        controller_with_plan.startPaintingFeatures(1, None)
        mock_assignments_service.getEditor.return_value.startEditCommand.assert_called_once_with(
            "Assign features to district 1")

        mock_assignments_service.reset_mock()

        controller_with_plan.startPaintingFeatures(1, 2)
        mock_assignments_service.getEditor.return_value.startEditCommand.assert_called_once_with(
            "Assign features to district 1 from 2")

    def test_paint_features(self, controller_with_plan: EditAssignmentsController, mock_plan, mock_assignments_editor: PlanAssignmentEditor, mock_assignments_service: AssignmentsService, mocker: MockerFixture):
        features = [mocker.create_autospec(spec=QgsFeature)]
        controller_with_plan.geoField = mock_plan.geoIdField
        controller_with_plan.paintFeatures(features, 1, None, False)
        mock_assignments_service.getEditor.assert_called_once()
        mock_assignments_editor.getDistFeatures.assert_not_called()
        mock_assignments_editor.assignFeaturesToDistrict.assert_called_once_with(features, 1)
        mock_assignments_editor.endEditCommand.assert_not_called()

    def test_paint_features_end_edit(self, controller_with_plan: EditAssignmentsController, mock_plan, mock_assignments_editor: PlanAssignmentEditor, mock_assignments_service: AssignmentsService, mocker: MockerFixture):
        features = [mocker.create_autospec(spec=QgsFeature)]
        controller_with_plan.geoField = mock_plan.geoIdField
        controller_with_plan.paintFeatures(features, 1, None, True)
        mock_assignments_service.getEditor.assert_called_once()
        mock_assignments_editor.getDistFeatures.assert_not_called()
        mock_assignments_editor.assignFeaturesToDistrict.assert_called_once_with(features, 1)
        mock_assignments_editor.endEditCommand.assert_called_once()

    def test_paint_features_with_geo_field(self, controller_with_plan: EditAssignmentsController, mock_assignments_editor: PlanAssignmentEditor, mock_assignments_service: AssignmentsService, mocker: MockerFixture):
        features = [mocker.create_autospec(spec=QgsFeature)]
        features[0].attribute.return_value = '011271001'
        matching_features = [mocker.create_autospec(spec=QgsFeature)]
        mock_assignments_editor.getDistFeatures.return_value = matching_features
        controller_with_plan.geoField = 'vtdid'
        controller_with_plan.paintFeatures(features, 1, None, False)
        mock_assignments_service.getEditor.assert_called_once()
        mock_assignments_editor.getDistFeatures.assert_called_once_with(
            'vtdid', {'011271001'}, 1, None)
        mock_assignments_editor.assignFeaturesToDistrict.assert_called_once_with(matching_features, 1)

    def test_end_paint_features(self, controller_with_plan: EditAssignmentsController, mock_assignments_editor: PlanAssignmentEditor, mock_assignments_service: AssignmentsService):
        controller_with_plan.endPaintingFeatures()
        mock_assignments_service.getEditor.assert_called_once()
        mock_assignments_editor.endEditCommand.assert_called_once()

    def test_cancel_paint_features(self, controller_with_plan: EditAssignmentsController, mock_assignments_editor: PlanAssignmentEditor, mock_assignments_service: AssignmentsService):
        controller_with_plan.cancelPaintingFeaturees()
        mock_assignments_service.getEditor.assert_called_once()
        mock_assignments_editor.cancelEditCommand.assert_called_once()

    def test_select_features(self, controller_with_plan: EditAssignmentsController, mock_plan, mock_assignments_editor: PlanAssignmentEditor, mock_assignments_service: AssignmentsService, mocker: MockerFixture):
        features = [mocker.create_autospec(spec=QgsFeature)]
        features[0].attribute.return_value = '011271001'
        matching_features = [mocker.create_autospec(spec=QgsFeature)]
        mock_assignments_editor.getDistFeatures.return_value = matching_features
        controller_with_plan.geoField = 'vtdid'
        controller_with_plan.selectFeatures(features, 1, None, Qgis.SelectBehavior.SetSelection)
        mock_assignments_service.getEditor.assert_called_once()
        mock_assignments_editor.getDistFeatures.assert_called_once_with(
            'vtdid', {'011271001'}, 1, None)
        mock_plan.assignLayer.selectByIds.assert_called_once()
