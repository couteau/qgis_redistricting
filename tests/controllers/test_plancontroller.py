from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from qgis.core import (
    QgsRasterLayer,
    QgsVectorLayer
)
from qgis.gui import Qgis
from qgis.PyQt.QtWidgets import (
    QAction,
    QDialog
)

from redistricting import (
    controllers,
    gui,
    services
)
from redistricting.models import RdsPlan
from redistricting.resources import *  # pylint: disable=wildcard-import, unused-wildcard-import


class TestPlanController:
    @pytest.fixture
    def mock_builder(self, mocker: MockerFixture):
        builder_class = mocker.patch('redistricting.controllers.PlanCtlr.PlanBuilder', spec=services.PlanBuilder)
        builder = builder_class.return_value
        builder.setName.return_value = builder
        builder.setNumDistricts.return_value = builder
        builder.setNumSeats.return_value = builder
        builder.setDescription.return_value = builder
        builder.setDeviation.return_value = builder
        builder.setGeoIdField.return_value = builder
        builder.setGeoDisplay.return_value = builder
        builder.setGeoLayer.return_value = builder
        builder.setGeoJoinField.return_value = builder
        builder.setPopLayer.return_value = builder
        builder.setPopJoinField.return_value = builder
        builder.setPopField.return_value = builder
        builder.setPopFields.return_value = builder
        builder.setDataFields.return_value = builder
        builder.setGeoFields.return_value = builder
        builder.setGeoPackagePath.return_value = builder
        return builder_class

    @pytest.fixture
    def mock_editor(self, mocker: MockerFixture):
        builder_class = mocker.patch('redistricting.controllers.PlanCtlr.PlanEditor', spec=services.PlanEditor)

        builder = builder_class.fromPlan.return_value
        builder.setName.return_value = builder
        builder.setNumDistricts.return_value = builder
        builder.setNumSeats.return_value = builder
        builder.setDescription.return_value = builder
        builder.setDeviation.return_value = builder
        builder.setGeoIdField.return_value = builder
        builder.setGeoDisplay.return_value = builder
        builder.setGeoLayer.return_value = builder
        builder.setPopLayer.return_value = builder
        builder.setGeoJoinField.return_value = builder
        builder.setPopField.return_value = builder
        builder.setPopFields.return_value = builder
        builder.setDataFields.return_value = builder
        builder.setGeoFields.return_value = builder
        return builder_class

    @pytest.fixture
    def mock_edit_dlg(self, mocker: MockerFixture, datadir):
        dlg_class = mocker.patch('redistricting.controllers.PlanCtlr.DlgEditPlan', spec=gui.DlgEditPlan)
        dlg = dlg_class.return_value
        dlg.planName.return_value = 'mocked'
        dlg.numDistricts.return_value = 5
        dlg.numSeats.return_value = 5
        dlg.description.return_value = 'mocked edit dialog plan'
        dlg.deviation.return_value = 0.03
        dlg.geoLayer.return_value = None
        dlg.popLayer.return_value = None
        dlg.geoIdField.return_value = 'geoid20'
        dlg.geoIdCaption.return_value = 'Block'
        dlg.joinField.return_value = 'geoid20'
        dlg.popField.return_value = 'pop_total'
        dlg.popFields.return_value = []
        dlg.dataFields.return_value = []
        dlg.geoFields.return_value = []
        dlg.gpkgPath.return_value = datadir / 'test_plan.gpkg'

        dlg.importPlan.return_value = False
        dlg.importPath.return_value = datadir / 'tuscaloosa_be.csv'
        dlg.importField.return_value = 'geoid20'
        dlg.importHeaderRow.return_value = True
        dlg.importDelim.return_value = ','
        dlg.importQuote.return_value = '"'
        dlg.importGeoCol.return_value = 0
        dlg.importDistCol.return_value = 1

        dlg.exec.return_value = QDialog.Accepted
        dlg.exec_.return_value = QDialog.Accepted
        return dlg_class

    @pytest.fixture
    def controller(self, qgis_iface, planmanager, mock_project, mock_toolbar, mocker: MockerFixture):
        layerTreeManager = mocker.create_autospec(spec=services.LayerTreeManager)
        styler = mocker.create_autospec(spec=services.PlanStylerService)
        updater = mocker.create_autospec(spec=services.DistrictUpdater)
        controller = controllers.PlanController(
            qgis_iface, mock_project, planmanager,
            mock_toolbar, layerTreeManager, styler, updater
        )
        controller.load()
        return controller

    @pytest.fixture
    def controller_with_active_plan(self, qgis_iface, planmanager_with_active_plan, mock_project, mock_toolbar, mocker: MockerFixture):
        layerTreeManager = mocker.create_autospec(spec=services.LayerTreeManager)
        styler = mocker.create_autospec(spec=services.PlanStylerService)
        updater = mocker.create_autospec(spec=services.DistrictUpdater)
        controller = controllers.PlanController(
            qgis_iface, mock_project, planmanager_with_active_plan,
            mock_toolbar, layerTreeManager, styler, updater
        )
        controller.load()
        return controller

    def test_enable_active_plan_actions(self, controller: controllers.PlanController, mock_plan):
        controller.addPlanToMenu(mock_plan)
        controller.enableActivePlanActions(mock_plan)
        assert controller.actionEditPlan.isEnabled()
        assert controller.actionImportAssignments.isEnabled()
        assert controller.actionImportShapefile.isEnabled()
        assert controller.actionExportPlan.isEnabled()
        assert controller.actionCopyPlan.isEnabled()
        assert controller.planActions.findChild(QAction, "test") is not None
        assert controller.planActions.findChild(QAction, "test").isChecked()

    def test_set_active_plan_none(self, controller: controllers.PlanController, mock_plan):
        controller.addPlanToMenu(mock_plan)
        controller.enableActivePlanActions(mock_plan)
        assert controller.actionEditPlan.isEnabled()
        assert controller.actionImportAssignments.isEnabled()
        assert controller.actionImportShapefile.isEnabled()
        assert controller.actionExportPlan.isEnabled()
        assert controller.actionCopyPlan.isEnabled()
        controller.enableActivePlanActions(None)
        assert not controller.actionEditPlan.isEnabled()
        assert not controller.actionImportAssignments.isEnabled()
        assert not controller.actionImportShapefile.isEnabled()
        assert not controller.actionExportPlan.isEnabled()
        assert not controller.actionCopyPlan.isEnabled()
        assert not controller.planActions.findChild(QAction, "test").isChecked()

    def test_enable_new_plan_has_vector_layer_enables(self, controller: controllers.PlanController, mocker: MockerFixture):
        assert not controller.actionNewPlan.isEnabled()
        controller.project.mapLayers.return_value = {
            uuid4(): mocker.create_autospec(spec=QgsVectorLayer, instance=True)
        }
        controller.enableNewPlan()
        assert controller.actionNewPlan.isEnabled()

    def test_enable_new_plan_no_vector_layer_disables(self, controller: controllers.PlanController):
        controller.actionNewPlan.setEnabled(True)
        assert controller.actionNewPlan.isEnabled()
        controller.project.mapLayers.return_value = {}
        controller.enableNewPlan()
        assert not controller.actionNewPlan.isEnabled()

    def test_enable_new_plan_raster_layer_disables(self, controller: controllers.PlanController, mocker: MockerFixture):
        controller.actionNewPlan.setEnabled(True)
        assert controller.actionNewPlan.isEnabled()
        controller.project.mapLayers.return_value = {
            uuid4(): mocker.create_autospec(spec=QgsRasterLayer, instance=True)
        }
        controller.enableNewPlan()
        assert not controller.actionNewPlan.isEnabled()

    @pytest.mark.parametrize(('remove_layers', 'delete_gpkg'), [(False, False), (True, False), (True, True)])
    def test_delete_plan(
        self,
        controller: controllers.PlanController,
        mock_plan,
        remove_layers,
        delete_gpkg,
        mocker: MockerFixture
    ):
        dlg = mocker.patch('redistricting.controllers.PlanCtlr.DlgConfirmDelete')
        dlg.return_value.exec.return_value = QDialog.Accepted
        dlg.return_value.removeLayers.return_value = remove_layers
        dlg.return_value.deleteGeoPackage.return_value = delete_gpkg

        controller.planManager.__contains__.return_value = False

        controller.deletePlan(mock_plan)
        dlg.assert_not_called()

        controller.planManager.__contains__.return_value = True
        path_mock = mocker.PropertyMock(return_value="non-existing-dir")
        type(mock_plan).geoPackagePath = path_mock
        controller.deletePlan(mock_plan)
        dlg.assert_called_once()
        if remove_layers:
            controller.layerTreeManager.removeGroup.assert_called_once()
            if delete_gpkg:
                path_mock.assert_called()
            else:
                path_mock.assert_not_called()
        else:
            controller.layerTreeManager.removeGroup.assert_not_called()
            path_mock.assert_not_called()

    def test_edit_plan_without_param_uses_active_plan(
        self,
        controller_with_active_plan: controllers.PlanController,
        mock_edit_dlg: MagicMock,
        mock_editor: MagicMock,
        mock_plan: RdsPlan
    ):
        builder = mock_editor.fromPlan.return_value

        controller_with_active_plan.editPlan()
        mock_edit_dlg.assert_called_once_with(mock_plan, controller_with_active_plan.iface.mainWindow())
        mock_editor.fromPlan.assert_called_once()
        builder.setName.assert_called_once_with('mocked')
        builder.updatePlan.assert_called_once()

    def test_edit_plan_with_param_uses_param(
        self,
        controller: controllers.PlanController,
        mock_edit_dlg: MagicMock,
        mock_editor: MagicMock,
        mock_plan: RdsPlan
    ):
        builder = mock_editor.fromPlan.return_value
        controller.editPlan(mock_plan)
        mock_edit_dlg.assert_called_once_with(mock_plan, controller.iface.mainWindow())
        mock_editor.fromPlan.assert_called_once()
        builder.setName.assert_called_once_with('mocked')
        builder.updatePlan.assert_called_once()

    def test_create_plan(
        self,
        controller: controllers.PlanController,
        mock_edit_dlg: MagicMock,
        mock_builder: MagicMock,
        mocker: MockerFixture,
    ):
        builder = mock_builder.return_value
        dlg = mock_edit_dlg.return_value
        importer_class = mocker.patch('redistricting.controllers.PlanCtlr.AssignmentImporter')
        layer = mocker.create_autospec(spec=QgsVectorLayer, instance=True)
        type(layer).id = mocker.PropertyMock(return_value=uuid4())
        controller.project.mapLayers.return_value = {layer.id: layer}
        dlg.geoLayer.return_value = layer

        controller.newPlan()
        mock_edit_dlg.assert_called_once()
        mock_builder.assert_called_once()
        builder.setName.assert_called_once_with('mocked')
        builder.createPlan.assert_called_once()
        importer_class.assert_not_called()

        dlg.importPlan.return_value = True
        controller.newPlan()
        importer_class.assert_called_once()

    def test_create_plan_no_layers_warns(
        self,
        controller: controllers.PlanController,
        mock_edit_dlg: MagicMock,
        mock_builder: MagicMock,
        qgis_iface,
    ):
        controller.newPlan()
        mock_edit_dlg.assert_not_called()
        mock_builder.assert_not_called()
        assert "Oops!:Cannot create a redistricting plan for an empty project. Try adding some layers." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_copy_plan_no_active_plan_warns(
        self,
        controller: controllers.PlanController,
        mocker: MockerFixture,
        qgis_iface
    ):
        dlg = mocker.patch('redistricting.controllers.PlanCtlr.DlgCopyPlan', spec=gui.DlgCopyPlan)

        controller.copyPlan()
        dlg.assert_not_called()
        assert "Oops!:Cannot copy: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_copy_plan_active_plan_executes_copy(
        self,
        controller_with_active_plan: controllers.PlanController,
        datadir,
        mocker: MockerFixture
    ):
        dlg = mocker.patch('redistricting.controllers.PlanCtlr.DlgCopyPlan', spec=gui.DlgCopyPlan)
        dlg.return_value.planName = 'copied'
        dlg.return_value.description = 'copy of plan'
        dlg.return_value.geoPackagePath = str(datadir / 'test_plan.gpkg')
        dlg.return_value.copyAssignments = False
        dlg.return_value.exec.return_value = QDialog.Accepted

        cpy = mocker.patch('redistricting.controllers.PlanCtlr.PlanCopier', spec=services.PlanCopier)

        controller_with_active_plan.copyPlan()
        dlg.assert_called_once()
        cpy.assert_called_once()
        dlg.return_value.exec.assert_called_once()
        cpy.return_value.copyPlan.assert_called_once_with(
            'copied', 'copy of plan', str(datadir / 'test_plan.gpkg'), False)

    def test_import_plan_no_active_plan_warns(
        self,
        controller: controllers.PlanController,
        mocker: MockerFixture,
        qgis_iface
    ):
        dlg_class = mocker.patch('redistricting.controllers.PlanCtlr.DlgImportPlan', spec=gui.DlgImportPlan)

        controller.importPlan()
        dlg_class.assert_not_called()
        assert "Oops!:Cannot import: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_import_plan_with_active_plan_executes_import(
        self,
        controller_with_active_plan: controllers.PlanController,
        datadir,
        mocker: MockerFixture
    ):
        dlg_class = mocker.patch('redistricting.controllers.PlanCtlr.DlgImportPlan', spec=gui.DlgImportPlan)
        dlgImportPlan = dlg_class.return_value
        dlgImportPlan.equivalencyFileName = str(datadir / 'tuscaloosa_be.csv')
        dlgImportPlan.joinField = 'geoid20'
        dlgImportPlan.headerRow = True
        dlgImportPlan.geoColumn = 0
        dlgImportPlan.distColumn = 1
        dlgImportPlan.delimiter = ','
        dlgImportPlan.quotechar = '"'
        dlgImportPlan.exec.return_value = QDialog.Accepted

        importer_class = mocker.patch('redistricting.controllers.PlanCtlr.AssignmentImporter',
                                      spec=services.AssignmentImporter)

        controller_with_active_plan.importPlan()
        dlg_class.assert_called_once()
        importer_class.assert_called_once()
        dlgImportPlan.exec.assert_called_once()

    def test_import_shapefile_no_active_plan_warns(
        self,
        controller: controllers.PlanController,
        mocker: MockerFixture,
        qgis_iface
    ):
        dlg_class = mocker.patch('redistricting.controllers.PlanCtlr.DlgImportShape', spec=gui.DlgImportShape)

        controller.importShapefile()
        dlg_class.assert_not_called()
        assert "Oops!:Cannot import: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_import_shapefile_with_active_plan_executes_import(
        self,
        controller_with_active_plan: controllers.PlanController,
        datadir,
        mocker: MockerFixture
    ):
        dlg_class = mocker.patch('redistricting.controllers.PlanCtlr.DlgImportShape', spec=gui.DlgImportShape)
        dlgImportPlan = dlg_class.return_value
        dlgImportPlan.shapefileFileName = str(datadir / 'tuscaloosa.shp')
        dlgImportPlan.distField = 'GEOID20'
        dlgImportPlan.nameField = None
        dlgImportPlan.membersField = None
        dlgImportPlan.exec.return_value = QDialog.Accepted

        importer_class = mocker.patch('redistricting.controllers.PlanCtlr.ShapefileImporter',
                                      spec=services.ShapefileImporter)

        controller_with_active_plan.importShapefile()
        dlg_class.assert_called_once()
        importer_class.assert_called_once()
        dlgImportPlan.exec.assert_called_once()
