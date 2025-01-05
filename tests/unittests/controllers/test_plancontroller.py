"""QGIS Redistricting Plugin - unit tests

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
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from qgis.core import (
    Qgis,
    QgsRasterLayer,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import pyqtBoundSignal
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
        builder_class = mocker.patch('redistricting.controllers.plan.PlanBuilder', spec=services.PlanBuilder)
        builder = builder_class.return_value
        builder.setName.return_value = builder
        builder.setNumDistricts.return_value = builder
        builder.setNumSeats.return_value = builder
        builder.setDescription.return_value = builder
        builder.setDeviation.return_value = builder
        builder.setDeviationType.return_value = builder
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
        builder_class = mocker.patch('redistricting.controllers.plan.PlanEditor', spec=services.PlanEditor)

        builder = builder_class.fromPlan.return_value
        builder.setName.return_value = builder
        builder.setNumDistricts.return_value = builder
        builder.setNumSeats.return_value = builder
        builder.setDescription.return_value = builder
        builder.setDeviation.return_value = builder
        builder.setDeviationType.return_value = builder
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
        dlg_class = mocker.patch('redistricting.controllers.plan.DlgEditPlan', spec=gui.DlgEditPlan)
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
    def mock_update_service(self, mocker: MockerFixture) -> services.DistrictUpdater:
        updater = mocker.create_autospec(spec=services.DistrictUpdater)
        updater.updateComplete = mocker.create_autospec(spec=pyqtBoundSignal)
        return updater

    @pytest.fixture
    def mock_import_service(self, mocker: MockerFixture) -> services.PlanImportService:
        importer = mocker.create_autospec(spec=services.PlanImportService)
        importer.importComplete = mocker.create_autospec(spec=pyqtBoundSignal)
        importer.importTerminated = mocker.create_autospec(spec=pyqtBoundSignal)
        return importer

    @pytest.fixture
    def mock_styler(self, mocker: MockerFixture) -> services.PlanStylerService:
        styler = mocker.create_autospec(spec=services.PlanStylerService)
        return styler

    @pytest.fixture
    def controller(self, qgis_iface, mock_planmanager, mock_project, mock_toolbar, mock_update_service, mock_styler, mock_import_service, mocker: MockerFixture):
        layerTreeManager = mocker.create_autospec(spec=services.LayerTreeManager)
        controller = controllers.PlanController(
            qgis_iface, mock_project, mock_planmanager,
            mock_toolbar, layerTreeManager, mock_styler, mock_update_service, mock_import_service
        )
        mocker.patch.object(controller, "startProgress")

        controller.load()
        yield controller
        controller.unload()

    @pytest.fixture
    def controller_with_active_plan(self, qgis_iface, mock_planmanager_with_active_plan, mock_project, mock_toolbar, mock_update_service, mock_styler, mock_import_service, mocker: MockerFixture):
        layerTreeManager = mocker.create_autospec(spec=services.LayerTreeManager)
        controller = controllers.PlanController(
            qgis_iface, mock_project, mock_planmanager_with_active_plan,
            mock_toolbar, layerTreeManager, mock_styler, mock_update_service, mock_import_service
        )
        mocker.patch.object(controller, "startProgress")
        controller.load()
        controller.addPlanToMenu(mock_planmanager_with_active_plan.activePlan)
        yield controller
        controller.unload()

    def test_add_plan_to_menu(self, controller: controllers.PlanController, mock_plan):
        assert len(controller.planMenu.actions()) == 0
        controller.addPlanToMenu(mock_plan)
        assert len(controller.planMenu.actions()) == 1

    def test_plan_added(self, controller: controllers.PlanController, mock_plan, mock_update_service: services.DistrictUpdater, mock_planmanager):
        assert len(controller.planMenu.actions()) == 0
        assert not controller.actionSelectPlan.isEnabled()
        mock_planmanager.__len__.return_value = 1
        controller.planAdded(mock_plan)
        assert len(controller.planMenu.actions()) == 1
        mock_update_service.watchPlan.assert_called_once_with(mock_plan)
        assert controller.actionSelectPlan.isEnabled()

    def test_append_plan(self, controller: controllers.PlanController, mock_plan, mock_planmanager, mock_project):
        controller.appendPlan(mock_plan, True)
        mock_planmanager.appendPlan.assert_called_once_with(mock_plan, True)
        mock_project.setDirty.assert_called_once()

    def test_activate_plan(self, controller: controllers.PlanController, mock_plan, mock_planmanager):
        controller.addPlanToMenu(mock_plan)
        controller.planActions.actions()[0].setChecked(True)
        controller.activatePlan(True)
        mock_planmanager.setActivePlan.assert_called_once()

    def test_remove_plan(self, controller_with_active_plan: controllers.PlanController, mock_plan):
        assert len(controller_with_active_plan.planMenu.actions()) == 1
        controller_with_active_plan.removePlanFromMenu(mock_plan)
        assert len(controller_with_active_plan.planMenu.actions()) == 0

    def test_plan_removed(self, controller_with_active_plan: controllers.PlanController, mock_plan, mock_update_service: services.DistrictUpdater):
        assert len(controller_with_active_plan.planMenu.actions()) == 1
        controller_with_active_plan.planRemoved(mock_plan)
        assert len(controller_with_active_plan.planMenu.actions()) == 0
        mock_update_service.unwatchPlan.assert_called_once_with(mock_plan)
        assert not controller_with_active_plan.actionSelectPlan.isEnabled()

    def test_clear_plan_menu(self, controller_with_active_plan: controllers.PlanController):
        assert len(controller_with_active_plan.planMenu.actions()) == 1
        controller_with_active_plan.clearPlanMenu()
        assert len(controller_with_active_plan.planMenu.actions()) == 0
        assert not controller_with_active_plan.actionSelectPlan.isEnabled()

    def test_enable_active_plan_actions(self, controller: controllers.PlanController, mock_plan):
        controller.addPlanToMenu(mock_plan)
        controller.enableActivePlanActions(mock_plan)
        assert controller.actionEditActivePlan.isEnabled()
        assert controller.actionImportAssignments.isEnabled()
        assert controller.actionImportShapefile.isEnabled()
        assert controller.actionExportPlan.isEnabled()
        assert controller.actionCopyPlan.isEnabled()
        assert controller.planActions.findChild(QAction, "test") is not None
        assert controller.planActions.findChild(QAction, "test").isChecked()

    def test_set_active_plan_none(self, controller: controllers.PlanController, mock_plan):
        controller.addPlanToMenu(mock_plan)
        controller.enableActivePlanActions(mock_plan)
        assert controller.actionEditActivePlan.isEnabled()
        assert controller.actionImportAssignments.isEnabled()
        assert controller.actionImportShapefile.isEnabled()
        assert controller.actionExportPlan.isEnabled()
        assert controller.actionCopyPlan.isEnabled()
        controller.enableActivePlanActions(None)
        assert not controller.actionEditActivePlan.isEnabled()
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
        dlg = mocker.patch('redistricting.controllers.plan.DlgConfirmDelete')
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
        controller.styler.stylePlan.assert_not_called()

    def test_edit_plan_with_no_active_plan_and_no_param_returns(
        self,
        controller: controllers.PlanController,
        mock_edit_dlg: MagicMock,
    ):
        controller.editPlan()
        mock_edit_dlg.assert_not_called()

    def test_edit_plan_with_changed_num_districts_calls_styler(
        self,
        controller_with_active_plan: controllers.PlanController,
        mock_edit_dlg: MagicMock,
        mock_editor: MagicMock,
        mock_plan: RdsPlan
    ):
        builder = mock_editor.fromPlan.return_value
        builder.modifiedFields = ['num-districts']
        controller_with_active_plan.editPlan()
        mock_edit_dlg.assert_called_once_with(mock_plan, controller_with_active_plan.iface.mainWindow())
        mock_editor.fromPlan.assert_called_once()
        controller_with_active_plan.styler.stylePlan.assert_called_once_with(mock_plan)

    def test_create_plan(
        self,
        controller: controllers.PlanController,
        mock_edit_dlg: MagicMock,
        mock_builder: MagicMock,
        mocker: MockerFixture,
    ):
        builder = mock_builder.return_value
        dlg = mock_edit_dlg.return_value
        layer = mocker.create_autospec(spec=QgsVectorLayer, instance=True)
        type(layer).id = mocker.PropertyMock(return_value=uuid4())
        controller.project.mapLayers.return_value = {layer.id: layer}
        dlg.geoLayer.return_value = layer

        controller.newPlan()
        mock_edit_dlg.assert_called_once()
        mock_builder.assert_called_once()
        builder.setName.assert_called_once_with('mocked')
        builder.createPlan.assert_called_once()
        controller.importService.importEquivalencyFile.assert_not_called()

        dlg.importPlan.return_value = True
        controller.newPlan()
        controller.importService.importEquivalencyFile.assert_called_once()

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
        dlg = mocker.patch('redistricting.controllers.plan.DlgCopyPlan', spec=gui.dlgcopy)

        controller.copyPlan()
        dlg.assert_not_called()
        assert "Oops!:Cannot copy: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

    @pytest.mark.parametrize('copy_assignments', [True, False])
    def test_copy_plan_active_plan_executes_copy(
        self,
        controller_with_active_plan: controllers.PlanController,
        copy_assignments,
        datadir,
        mocker: MockerFixture
    ):
        dlg = mocker.patch('redistricting.controllers.plan.DlgCopyPlan', spec=gui.DlgCopyPlan)
        dlg.return_value.planName = 'copied'
        dlg.return_value.description = 'copy of plan'
        dlg.return_value.geoPackagePath = str(datadir / 'test_plan.gpkg')
        dlg.return_value.copyAssignments = copy_assignments
        dlg.return_value.exec.return_value = QDialog.Accepted

        cpy = mocker.patch('redistricting.controllers.plan.PlanCopier', spec=services.PlanCopier)

        controller_with_active_plan.copyPlan()
        dlg.assert_called_once()
        cpy.assert_called_once()
        dlg.return_value.exec.assert_called_once()
        cpy.return_value.copyPlan.assert_called_once_with(
            'copied', 'copy of plan', str(datadir / 'test_plan.gpkg'), copy_assignments)

    def test_import_plan_no_active_plan_warns(
        self,
        controller: controllers.PlanController,
        mocker: MockerFixture,
        qgis_iface
    ):
        dlg_class = mocker.patch('redistricting.controllers.plan.DlgImportPlan', spec=gui.dlgimportequivalency)

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
        dlg_class = mocker.patch('redistricting.controllers.plan.DlgImportPlan', spec=gui.DlgImportPlan)
        dlgImportPlan = dlg_class.return_value
        dlgImportPlan.equivalencyFileName = str(datadir / 'tuscaloosa_be.csv')
        dlgImportPlan.joinField = 'geoid20'
        dlgImportPlan.headerRow = True
        dlgImportPlan.geoColumn = 0
        dlgImportPlan.distColumn = 1
        dlgImportPlan.delimiter = ','
        dlgImportPlan.quotechar = '"'
        dlgImportPlan.exec.return_value = QDialog.Accepted

        importService = mocker.patch.object(controller_with_active_plan, 'importService')

        controller_with_active_plan.importPlan()
        dlg_class.assert_called_once()
        importService.importEquivalencyFile.assert_called_once()
        dlgImportPlan.exec.assert_called_once()

    def test_import_shapefile_no_active_plan_warns(
        self,
        controller: controllers.PlanController,
        mocker: MockerFixture,
        qgis_iface
    ):
        dlg_class = mocker.patch('redistricting.controllers.plan.DlgImportShape', spec=gui.DlgImportShape)

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
        dlg_class = mocker.patch('redistricting.controllers.plan.DlgImportShape', spec=gui.DlgImportShape)
        dlgImportPlan = dlg_class.return_value
        dlgImportPlan.shapefileFileName = str(datadir / 'tuscaloosa.shp')
        dlgImportPlan.distField = 'GEOID20'
        dlgImportPlan.nameField = None
        dlgImportPlan.membersField = None
        dlgImportPlan.exec.return_value = QDialog.Accepted

        importService = mocker.patch.object(controller_with_active_plan, 'importService')

        controller_with_active_plan.importShapefile()
        dlg_class.assert_called_once()
        importService.importShapeFile.assert_called_once()
        dlgImportPlan.exec.assert_called_once()

    def test_export_plan_no_active_plan_warns(
        self,
        controller: controllers.PlanController,
        mocker: MockerFixture,
        qgis_iface
    ):
        dlg_class = mocker.patch('redistricting.controllers.plan.DlgExportPlan', spec=gui.dlgexport)

        controller.exportPlan()
        dlg_class.assert_not_called()
        assert "Oops!:Cannot export: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_export_plan_with_active_plan_executes_export(
        self,
        controller_with_active_plan: controllers.PlanController,
        datadir,
        mocker: MockerFixture
    ):
        mocker.patch('redistricting.controllers.plan.GeoFieldsModel')
        dlg_class = mocker.patch('redistricting.controllers.plan.DlgExportPlan')
        dlgExportPlan = dlg_class.return_value

        dlgExportPlan.exportEquivalency = True
        dlgExportPlan.equivalencyFileName = str(datadir / 'tuscaloosa_be.csv')
        dlgExportPlan.equivalencyGeography = controller_with_active_plan.planManager.activePlan.geoFields[0]
        dlgExportPlan.exportShapefile = True
        dlgExportPlan.shapefileFileName = str(datadir / 'tuscaloosa.shp')
        dlgExportPlan.includeUnassigned = False
        dlgExportPlan.includeDemographics = True
        dlgExportPlan.includeMetrics = True
        dlgExportPlan.exec.return_value = QDialog.Accepted

        exporter_class = mocker.patch('redistricting.controllers.plan.PlanExporter',
                                      spec=services.PlanExporter)

        controller_with_active_plan.exportPlan()
        dlg_class.assert_called_once()
        exporter_class.assert_called_once()
        dlgExportPlan.exec.assert_called_once()

    def test_trigger_update(self, controller_with_active_plan: controllers.PlanController, mock_update_service, mock_plan):
        controller_with_active_plan.triggerUpdate(mock_plan)
        mock_update_service.updateDistricts.assert_called_once()
