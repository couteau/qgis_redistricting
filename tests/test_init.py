"""Test redististricting plugin initialization"""
import pathlib
import configparser
from uuid import uuid4
import pytest
from pytestqt.plugin import QtBot
from pytest_mock.plugin import MockerFixture
from qgis.core import Qgis, QgsProject
from qgis.PyQt.QtCore import Qt, QObject
from qgis.PyQt.QtWidgets import QProgressDialog, QPushButton


class TestPluginInit:
    @pytest.fixture
    def plugin(self, qgis_iface, mocker: MockerFixture):
        import redistricting  # pylint: disable=import-outside-toplevel
        settings = mocker.patch('redistricting.redistricting.QSettings')
        settings.return_value = mocker.Mock()
        settings_obj = settings.return_value
        settings_obj.value.return_value = 'en_US'
        qgis_iface.vectorMenu = mocker.MagicMock()
        qgis_iface.addPluginToVectorMenu = mocker.MagicMock()
        qgis_iface.removeDockWidget = mocker.MagicMock()
        qgis_iface.removePluginVectorMenu = mocker.MagicMock()

        return redistricting.classFactory(qgis_iface)

    @pytest.fixture
    def plugin_with_gui(self, plugin):
        plugin.initGui()
        yield plugin
        plugin.unload()

    @pytest.fixture
    def plugin_with_plan(self, plugin_with_gui, plan):
        plugin_with_gui.appendPlan(plan)
        return plugin_with_gui

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

    def test_append_plan(self, plugin, plan: QObject):
        plugin.appendPlan(plan)
        assert len(plugin.redistrictingPlans) == 1
        assert plan.isSignalConnected(plan.metaObject().method(plan.metaObject().indexOfMethod(
            'planChanged(PyQt_PyObject,QString,PyQt_PyObject,PyQt_PyObject)'))
        )

    def test_remove_plan(self, plugin_with_plan, plan, qtbot: QtBot):
        with qtbot.wait_signal(QgsProject.instance().layersRemoved):
            plugin_with_plan.removePlan(plan)
        assert len(plugin_with_plan.redistrictingPlans) == 0
        assert len(QgsProject.instance().mapLayers()) == 1

    def test_set_active_plan(self, plugin_with_plan, plan):
        plugin_with_plan.setActivePlan(plugin_with_plan.redistrictingPlans[0])
        assert plugin_with_plan.activePlan == plan
        assert plugin_with_plan.mapTool is not None

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
        assert plugin_with_plan.mapTool is None

    def test_set_active_invalid_plan(self, plugin, plan_with_pop_layer):
        plugin.appendPlan(plan_with_pop_layer)
        plugin.setActivePlan(plan_with_pop_layer)
        assert plugin.activePlan is None

    def test_remove_layer(self, plugin_with_gui, block_layer, qtbot: QtBot):
        with qtbot.wait_signal(QgsProject.instance().layersRemoved):
            QgsProject.instance().removeMapLayer(block_layer.id())
        qtbot.wait(100)
        assert not plugin_with_gui.actionNewPlan.isEnabled()

    def test_clear(self, plugin_with_plan):
        plugin_with_plan.clear()
        assert len(plugin_with_plan.redistrictingPlans) == 0
        assert plugin_with_plan.activePlan is None
        assert plugin_with_plan.actionNewPlan.isEnabled()

    def test_clear_disables_action(self, plugin_with_gui, block_layer):
        QgsProject.instance().removeMapLayer(block_layer.id())
        plugin_with_gui.clear()
        assert not plugin_with_gui.actionNewPlan.isEnabled()
