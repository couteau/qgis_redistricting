"""Test redististricting plugin initialization"""
import configparser
import pathlib
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pytest_mock.plugin import MockerFixture
from pytestqt.plugin import QtBot
from qgis.core import (
    Qgis,
    QgsProject,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    QObject,
    Qt
)
from qgis.PyQt.QtWidgets import (
    QDialog,
    QProgressDialog,
    QPushButton
)

from redistricting import (
    classFactory,
    redistricting
)
from redistricting.core import FieldList
from redistricting.gui import (
    DlgCopyPlan,
    DlgEditPlan,
    DlgImportPlan,
    DlgImportShape
)


class TestPluginInit:

    @pytest.fixture
    def plugin(self, qgis_iface, mocker: MockerFixture):
        settings = mocker.patch('redistricting.redistricting.QSettings')
        settings_obj = settings.return_value
        settings_obj.value.return_value = 'en_US'
        qgis_iface.addCustomActionForLayerType = mocker.MagicMock()
        qgis_iface.addCustomActionForLayer = mocker.MagicMock()
        qgis_iface.vectorMenu = mocker.MagicMock()
        qgis_iface.addPluginToVectorMenu = mocker.MagicMock()
        qgis_iface.removeDockWidget = mocker.MagicMock()
        qgis_iface.removePluginVectorMenu = mocker.MagicMock()
        qgis_iface.layerTreeView = mocker.MagicMock()

        return classFactory(qgis_iface)

    @pytest.fixture
    def plugin_with_gui(self, plugin):
        plugin.initGui()
        yield plugin
        plugin.unload()

    @pytest.fixture
    def plugin_with_plan(self, plugin_with_gui, plan):
        plugin_with_gui.redistrictingPlans.append(plan)
        return plugin_with_gui

    @pytest.fixture
    def plugin_with_project(self, plugin_with_gui, datadir, qtbot: QtBot, qgis_new_project):  # pylint: disable=unused-argument
        project = QgsProject.instance()
        with qtbot.waitSignal(project.readProject):
            project.read(str((datadir / 'test_project.qgs').resolve()))
        yield plugin_with_gui
        project.clear()

    @pytest.fixture
    def mock_builder(self, mocker: MockerFixture):
        builder_class = mocker.patch('redistricting.redistricting.PlanBuilder', spec=redistricting.PlanBuilder)
        builder = builder_class.return_value
        builder.setName.return_value = builder
        builder.setNumDistricts.return_value = builder
        builder.setNumSeats.return_value = builder
        builder.setDescription.return_value = builder
        builder.setDeviation.return_value = builder
        builder.setGeoIdField.return_value = builder
        builder.setGeoDisplay.return_value = builder
        builder.setGeoLayer.return_value = builder
        builder.setPopLayer.return_value = builder
        builder.setJoinField.return_value = builder
        builder.setPopField.return_value = builder
        builder.setPopFields.return_value = builder
        builder.setDataFields.return_value = builder
        builder.setGeoFields.return_value = builder
        builder.setGeoPackagePath.return_value = builder
        return builder_class

    @pytest.fixture
    def mock_editor(self, mocker: MockerFixture):
        builder_class = mocker.patch('redistricting.redistricting.PlanEditor', spec=redistricting.PlanEditor)
        mocker.patch.object(redistricting.PlanEditor, 'fromPlan', builder_class)
        builder = builder_class.return_value
        builder.setName.return_value = builder
        builder.setNumDistricts.return_value = builder
        builder.setNumSeats.return_value = builder
        builder.setDescription.return_value = builder
        builder.setDeviation.return_value = builder
        builder.setGeoIdField.return_value = builder
        builder.setGeoDisplay.return_value = builder
        builder.setGeoLayer.return_value = builder
        builder.setPopLayer.return_value = builder
        builder.setJoinField.return_value = builder
        builder.setPopField.return_value = builder
        builder.setPopFields.return_value = builder
        builder.setDataFields.return_value = builder
        builder.setGeoFields.return_value = builder
        return builder_class

    @pytest.fixture
    def mock_edit_dlg(self, mocker: MockerFixture, datadir):
        dlg_class = mocker.patch('redistricting.redistricting.DlgEditPlan', spec=DlgEditPlan)
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
        dlg.popFields.return_value = FieldList()
        dlg.dataFields.return_value = FieldList()
        dlg.geoFields.return_value = FieldList()
        dlg.gpkgPath.return_value = datadir / 'test_plan.gpkg'

        dlg.importPlan.return_value = False
        dlg.importPath.return_value = datadir / 'tuscaloosa_be.csv'
        dlg.importField.return_value = 'geoid20'
        dlg.importHeaderRow.return_value = True
        dlg.importDelim.return_value = ','
        dlg.importQuote.return_value = '"'
        dlg.importGeoCol.return_value = 0
        dlg.importDistCol.return_value = 1

        dlg.exec_.return_value = QDialog.Accepted

        return dlg_class

    def test_metadata(self):
        """Test that the plugin metadata.txt will validate on plugins.qgis.org."""

        # You should update this list according to the latest in
        # https://github.com/qgis/qgis-django/blob/master/qgis-app/plugins/validator.py

        required_metadata = [
            'name',
            'description',
            'version',
            'qgisMinimumVersion',
            'author',
            'email',
            'about',
            'tracker',
            'repository'
        ]

        file_path = (pathlib.Path(__file__).parent.parent / 'redistricting' / 'metadata.txt').resolve()
        metadata = []
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read(file_path)
        message = f'Cannot find a section named "general" in {file_path}'
        assert parser.has_section('general'), message
        metadata.extend(parser.items('general'))

        for expectation in required_metadata:
            message = f'Cannot find metadata "{expectation}" in metadata source ({file_path}).'
            assert expectation in dict(metadata), message

    def test_init(self, plugin):
        assert plugin.name == 'Redistricting'

    def test_init_gui(self, plugin):
        plugin.initGui()
        assert plugin.projectSignalsConnected
        plugin.unload()
        assert not plugin.projectSignalsConnected

    def test_add_layer_enables_newplan(self, plugin, datadir, qtbot):
        plugin.initGui()
        assert not plugin.actionNewPlan.isEnabled()
        with qtbot.waitSignal(QgsProject.instance().layersAdded):
            gpkg = (datadir / 'tuscaloosa_blocks.gpkg').resolve()
            layer = QgsVectorLayer(f'{gpkg}|layername=plans', 'blocks', 'ogr')
            QgsProject.instance().addMapLayer(layer)
        assert plugin.actionNewPlan.isEnabled()
        plugin.unload()

    def test_progress(self, plugin):
        d: QProgressDialog = plugin.startProgress('Progress test')
        assert d is not None
        assert d.labelText() == 'Progress test'
        assert d.findChild(QPushButton) is not None
        assert d.findChild(QPushButton).text() == 'Cancel'

    def test_progress_no_cancel(self, plugin):
        d: QProgressDialog = plugin.startProgress('Progress test', canCancel=False)
        assert d is not None
        assert d.labelText() == 'Progress test'
        assert d.findChild(QPushButton) is None

    def test_progress_cancel(self, plugin, qtbot: QtBot, qgis_iface):
        d: QProgressDialog = plugin.startProgress('Progress test')
        with qtbot.waitSignal(d.canceled):
            b = d.findChild(QPushButton)
            qtbot.mouseClick(b, Qt.LeftButton)
        m = qgis_iface.messageBar().get_messages(Qgis.Warning)
        assert 'Canceled:Progress test canceled' in m

    def test_progress_create_new_dialog_closes_old_dialog(self, plugin, qtbot: QtBot):
        d1: QProgressDialog = plugin.startProgress('Progress test1')
        with qtbot.wait_exposed(d1):
            d1.show()
        d2: QProgressDialog = plugin.startProgress('Progress test2', canCancel=False)
        assert d1.isHidden()
        assert d2 != d1
        with qtbot.wait_exposed(d2):
            d2.show()
        d3: QProgressDialog = plugin.startProgress('Progress test3')
        assert d2.isHidden()
        assert d3 != d2
        d3.hide()

    def test_append_plan(self, plugin_with_gui, plan: QObject):
        plugin_with_gui.appendPlan(plan)
        assert len(plugin_with_gui.redistrictingPlans) == 1
        assert plan.isSignalConnected(plan.metaObject().method(plan.metaObject().indexOfMethod(
            'planChanged(PyQt_PyObject,QString,PyQt_PyObject,PyQt_PyObject)'))
        )

    def test_remove_plan(self, plugin_with_plan, plan, qtbot: QtBot):
        plugin_with_plan.setActivePlan(plan)
        with qtbot.wait_signal(QgsProject.instance().layersRemoved):
            plugin_with_plan.removePlan(plan)
        assert len(plugin_with_plan.redistrictingPlans) == 0
        assert len(QgsProject.instance().mapLayers()) == 1
        assert plugin_with_plan.activePlan is None

    def test_remove_plan_del_gpkg(self, plugin_with_plan, plan, datadir, qtbot: QtBot):
        assert (datadir / 'tuscaloosa_plan.gpkg').resolve().exists()
        with qtbot.wait_signal(QgsProject.instance().layersRemoved):
            plugin_with_plan.removePlan(plan, True, True)
        assert len(plugin_with_plan.redistrictingPlans) == 0
        assert len(QgsProject.instance().mapLayers()) == 1
        assert not (datadir / 'tuscaloosa_plan.gpkg').resolve().exists()

    def test_set_active_plan(self, plugin_with_plan, plan):
        plugin_with_plan.setActivePlan(plugin_with_plan.redistrictingPlans[0])
        assert plugin_with_plan.activePlan == plan
        assert plugin_with_plan.mapTool is not None
        assert plugin_with_plan.actionStartPaintDistricts.isEnabled()
        assert plugin_with_plan.actionEditPlan.isEnabled()
        assert plugin_with_plan.actionImportAssignments.isEnabled()
        assert plugin_with_plan.actionImportShapefile.isEnabled()
        assert plugin_with_plan.actionExportPlan.isEnabled()
        assert plugin_with_plan.actionCopyPlan.isEnabled()

    def test_set_active_plan_uuid(self, plugin_with_plan, plan):
        plugin_with_plan.setActivePlan(plan.id)
        assert plugin_with_plan.activePlan == plan
        assert plugin_with_plan.mapTool is not None

    def test_set_active_plan_uuid_not_in_list(self, plugin_with_plan):
        plugin_with_plan.setActivePlan(uuid4())
        assert plugin_with_plan.activePlan is None

    def test_set_active_plan_none(self, plugin_with_plan):
        plugin_with_plan.setActivePlan(plugin_with_plan.redistrictingPlans[0])
        plugin_with_plan.setActivePlan(None)
        assert plugin_with_plan.activePlan is None
        assert not plugin_with_plan.mapTool.canActivate()
        assert not plugin_with_plan.actionStartPaintDistricts.isEnabled()
        assert not plugin_with_plan.actionEditPlan.isEnabled()
        assert not plugin_with_plan.actionImportAssignments.isEnabled()
        assert not plugin_with_plan.actionImportShapefile.isEnabled()
        assert not plugin_with_plan.actionExportPlan.isEnabled()
        assert not plugin_with_plan.actionCopyPlan.isEnabled()

    def test_set_active_invalid_plan(self, plugin_with_gui, minimal_plan):
        plugin_with_gui.appendPlan(minimal_plan)
        plugin_with_gui.setActivePlan(minimal_plan)
        assert plugin_with_gui.activePlan is None

    def test_remove_layer(self, plugin_with_gui, block_layer, qtbot: QtBot):
        with qtbot.wait_signal(QgsProject.instance().layersRemoved):
            QgsProject.instance().removeMapLayer(block_layer.id())
        qtbot.wait(50)
        assert not plugin_with_gui.actionNewPlan.isEnabled()

    @pytest.mark.parametrize('layer', [
        pytest.lazy_fixture("block_layer"),
        pytest.lazy_fixture("assign_layer"),
        pytest.lazy_fixture("dist_layer")
    ])
    def test_remove_layer_removes_plan(self, plugin_with_plan, layer, qtbot: QtBot):
        with qtbot.wait_signal(QgsProject.instance().layersRemoved):
            QgsProject.instance().removeMapLayer(layer.id())
        assert not plugin_with_plan.redistrictingPlans

    def test_clear(self, plugin_with_plan):
        plugin_with_plan.clear()
        assert len(plugin_with_plan.redistrictingPlans) == 0
        assert plugin_with_plan.activePlan is None
        assert plugin_with_plan.actionNewPlan.isEnabled()

    def test_clear_disables_action(self, plugin_with_gui, block_layer):
        QgsProject.instance().removeMapLayer(block_layer.id())
        plugin_with_gui.clear()
        assert not plugin_with_gui.actionNewPlan.isEnabled()

    def test_open_project(self, plugin_with_gui, datadir):
        project = QgsProject.instance()
        project.read(str((datadir / 'test_project.qgs').resolve()))
        assert len(project.mapLayers()) == 3
        assert len(plugin_with_gui.redistrictingPlans) == 1
        plan: redistricting.RedistrictingPlan = plugin_with_gui.activePlan
        assert plan.totalPopulation > 0 or plan.districts._needUpdate  # pylint: disable=protected-access

    def test_close_project(self, plugin_with_project):
        QgsProject.instance().clear()
        assert not plugin_with_project.redistrictingPlans
        assert not plugin_with_project.actionNewPlan.isEnabled()

    def test_write_project(self, plugin_with_project: redistricting.Redistricting, mocker: MockerFixture):
        storage = mocker.patch('redistricting.redistricting.ProjectStorage')
        plan = plugin_with_project.activePlan
        plan._setDeviation(0.05)  # pylint: disable=protected-access
        assert QgsProject.instance().isDirty()
        QgsProject.instance().write()
        storage.assert_called_once()

    def test_write_project_no_plan(self, plugin_with_gui, mocker: MockerFixture):  # pylint: disable=unused-argument
        storage = mocker.patch('redistricting.redistricting.ProjectStorage')
        project = QgsProject.instance()
        project.write()
        storage.assert_not_called()

    def test_check_active_plan(self, plugin_with_gui, datadir, qtbot, qgis_iface):
        result = plugin_with_gui.checkActivePlan('test')
        assert not result
        assert "Oops!:Cannot test: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

        project = QgsProject.instance()
        with qtbot.waitSignal(project.readProjectWithContext):
            project.read(str((datadir / 'test_project.qgs').resolve()))

        result = plugin_with_gui.checkActivePlan('test')
        assert result

    def test_create_district(self, plugin_with_plan, mocker: MockerFixture, qgis_iface):
        result = plugin_with_plan.createDistrict()
        assert result is None
        assert "Oops!:Cannot create district: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

        plugin_with_plan.setActivePlan(plugin_with_plan.redistrictingPlans[0])
        dlgcls = mocker.patch('redistricting.redistricting.DlgNewDistrict')
        dlg = dlgcls.return_value
        dlg.exec_.return_value = QDialog.Accepted
        add = mocker.patch.object(plugin_with_plan.activePlan, 'addDistrict')
        settarget = mocker.patch.object(plugin_with_plan.dockwidget, 'setTargetDistrict')
        result = plugin_with_plan.createDistrict()
        assert result is not None
        add.assert_called_once()
        settarget.assert_called_once()

        dlg.exec_.return_value = QDialog.Rejected
        result = plugin_with_plan.createDistrict()
        assert result is None

    def test_create_district_all_allocated(self, plugin_with_project, qgis_iface):
        result = plugin_with_project.createDistrict()
        assert result is None
        assert 'Warning:All districts have already been allocated' in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_edit_signals(self, plugin_with_project: redistricting.Redistricting, qtbot):
        plan = plugin_with_project.activePlan
        with qtbot.wait_signal(plan.assignLayer.editingStarted):
            plan.assignLayer.startEditing()
        assert plugin_with_project.actionCommitPlanChanges.isEnabled()
        assert plugin_with_project.actionRollbackPlanChanges.isEnabled()
        with qtbot.wait_signal(plan.assignLayer.editingStopped):
            plan.assignLayer.rollBack(True)
        assert not plugin_with_project.actionCommitPlanChanges.isEnabled()
        assert not plugin_with_project.actionRollbackPlanChanges.isEnabled()

    def test_delete_plan(
        self,
        plugin_with_project: redistricting.Redistricting,
        minimal_plan,
        mocker: MockerFixture
    ):
        dlg = mocker.patch('redistricting.redistricting.DlgConfirmDelete')
        dlg.return_value.exec_.return_value = QDialog.Accepted
        dlg.return_value.removeLayers.return_value = False
        dlg.return_value.deleteGeoPackage.return_value = False

        plugin_with_project.deletePlan(minimal_plan)
        dlg.assert_not_called()

        plugin_with_project.deletePlan(plugin_with_project.redistrictingPlans[0])
        dlg.assert_called_once()

    def test_edit_plan(
        self,
        plugin_with_project: redistricting.Redistricting,
        mock_edit_dlg: MagicMock,
        mock_editor: MagicMock
    ):
        builder = mock_editor.return_value

        plugin_with_project.editPlan()
        mock_edit_dlg.assert_called_once()
        mock_editor.assert_called_once()
        builder.setName.assert_called_once_with('mocked')
        builder.updatePlan.assert_called_once()

    def test_create_plan(
        self,
        plugin_with_project: redistricting.Redistricting,
        mock_edit_dlg: MagicMock,
        mock_builder: MagicMock,
        mocker: MockerFixture,
        qgis_iface
    ):
        builder = mock_builder.return_value
        importer_class = mocker.patch('redistricting.redistricting.AssignmentImporter')

        plugin_with_project.project.setDirty(True)
        plugin_with_project.newPlan()
        mock_edit_dlg.assert_not_called()
        mock_builder.assert_not_called()
        assert "Wait!:Please save your project before creating a redistricting plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

        plugin_with_project.project.setDirty(False)
        plugin_with_project.newPlan()
        mock_edit_dlg.assert_called_once()
        mock_builder.assert_called_once()
        builder.setName.assert_called_once_with('mocked')
        builder.createPlan.assert_called_once()
        importer_class.assert_not_called()

        dlg = mock_edit_dlg.return_value
        dlg.importPlan.return_value = True
        plugin_with_project.newPlan()
        importer_class.assert_called_once()

    def test_create_plan_no_layers_warns(
        self,
        plugin_with_gui: redistricting.Redistricting,
        mock_edit_dlg: MagicMock,
        mock_builder: MagicMock,
        qgis_iface,
    ):
        plugin_with_gui.newPlan()
        mock_edit_dlg.assert_not_called()
        mock_builder.assert_not_called()
        assert "Oops!:Cannot create a redistricting plan for an empty project. Try adding some layers." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

    def test_copy_plan(
        self,
        plugin_with_project: redistricting.Redistricting,
        datadir,
        mocker: MockerFixture,
        qgis_iface
    ):
        dlg = mocker.patch('redistricting.redistricting.DlgCopyPlan', spec=DlgCopyPlan)
        dlg.return_value.planName = 'copied'
        dlg.return_value.description = 'copy of plan'
        dlg.return_value.geoPackagePath = str(datadir / 'test_plan.gpkg')
        dlg.return_value.copyAssignments = False
        dlg.return_value.exec_.return_value = QDialog.Accepted

        cpy = mocker.patch('redistricting.redistricting.PlanCopier', spec=redistricting.PlanCopier)

        plugin_with_project.setActivePlan(None)
        plugin_with_project.copyPlan()
        dlg.assert_not_called()
        assert "Oops!:Cannot copy: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

        plugin_with_project.setActivePlan(plugin_with_project.redistrictingPlans[0])
        plugin_with_project.copyPlan()
        dlg.assert_called_once()
        cpy.assert_called_once()
        dlg.return_value.exec_.assert_called_once()
        cpy.return_value.copyPlan.assert_called_once_with(
            'copied', 'copy of plan', str(datadir / 'test_plan.gpkg'), False)

    def test_import_plan(
        self,
        plugin_with_project: redistricting.Redistricting,
        datadir,
        mocker: MockerFixture,
        qgis_iface
    ):
        dlg_class = mocker.patch('redistricting.redistricting.DlgImportPlan', spec=DlgImportPlan)
        dlgImportPlan = dlg_class.return_value
        dlgImportPlan.equivalencyFileName = str(datadir / 'tuscaloosa_be.csv')
        dlgImportPlan.joinField = 'geoid20'
        dlgImportPlan.headerRow = True
        dlgImportPlan.geoColumn = 0
        dlgImportPlan.distColumn = 1
        dlgImportPlan.delimiter = ','
        dlgImportPlan.quotechar = '"'
        dlgImportPlan.exec_.return_value = QDialog.Accepted

        importer_class = mocker.patch('redistricting.redistricting.AssignmentImporter',
                                      spec=redistricting.AssignmentImporter)

        plugin_with_project.setActivePlan(None)
        plugin_with_project.importPlan()
        dlg_class.assert_not_called()
        assert "Oops!:Cannot import: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

        plugin_with_project.setActivePlan(plugin_with_project.redistrictingPlans[0])
        plugin_with_project.importPlan()
        dlg_class.assert_called_once()
        importer_class.assert_called_once()
        dlgImportPlan.exec_.assert_called_once()

    def test_import_shapefile(
        self,
        plugin_with_project: redistricting.Redistricting,
        datadir,
        mocker: MockerFixture,
        qgis_iface
    ):
        dlg_class = mocker.patch('redistricting.redistricting.DlgImportShape', spec=DlgImportShape)
        dlgImportPlan = dlg_class.return_value
        dlgImportPlan.shapefileFileName = str(datadir / 'tuscaloosa.shp')
        dlgImportPlan.distField = 'GEOID20'
        dlgImportPlan.nameField = None
        dlgImportPlan.membersField = None
        dlgImportPlan.exec_.return_value = QDialog.Accepted

        importer_class = mocker.patch('redistricting.redistricting.ShapefileImporter',
                                      spec=redistricting.ShapefileImporter)

        plugin_with_project.setActivePlan(None)
        plugin_with_project.importShapefile()
        dlg_class.assert_not_called()
        assert "Oops!:Cannot import: no active redistricting plan. Try creating a new plan." \
            in qgis_iface.messageBar().get_messages(Qgis.Warning)

        plugin_with_project.setActivePlan(plugin_with_project.redistrictingPlans[0])
        plugin_with_project.importShapefile()
        dlg_class.assert_called_once()
        importer_class.assert_called_once()
        dlgImportPlan.exec_.assert_called_once()
