"""Test redististricting plugin initialization"""
import configparser
import pathlib

import pytest
from pytest_lazy_fixtures import lf
from pytest_mock.plugin import MockerFixture
from pytestqt.plugin import QtBot
from qgis.core import QgsProject

from redistricting import (
    classFactory,
    redistricting
)

# pylint: disable=unused-argument


class TestPluginInit:

    @pytest.fixture
    def plugin(self, qgis_iface, mocker: MockerFixture):
        settings = mocker.patch('redistricting.redistricting.QSettings')
        settings_obj = settings.return_value
        settings_obj.value.return_value = 'en_US'
        qgis_iface.addCustomActionForLayerType = mocker.MagicMock()
        qgis_iface.removeCustomActionForLayerType = mocker.MagicMock()
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
    def plugin_with_plan(self, plugin_with_gui: redistricting.Redistricting, plan):
        plugin_with_gui.planManager.appendPlan(plan)
        return plugin_with_gui

    @pytest.fixture
    def plugin_with_project(self, plugin_with_gui, datadir, qtbot: QtBot, qgis_new_project):  # pylint: disable=unused-argument
        project = QgsProject.instance()
        with qtbot.waitSignal(project.readProject):
            project.read(str((datadir / 'test_project.qgs').resolve()))
        yield plugin_with_gui
        project.clear()

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
        plugin.unload()

    @pytest.mark.parametrize('layer', [
        lf("block_layer"),
        lf("assign_layer"),
        lf("dist_layer")
    ])
    def test_remove_layer_removes_plan(self, plugin_with_plan: redistricting.Redistricting, layer, qtbot: QtBot):
        with qtbot.wait_signal(QgsProject.instance().layersRemoved):
            QgsProject.instance().removeMapLayer(layer.id())
        assert len(plugin_with_plan.planManager) == 0

    def test_clear_disables_action(self, plugin_with_gui: redistricting.Redistricting, block_layer):
        QgsProject.instance().removeMapLayer(block_layer.id())
        plugin_with_gui.clear()
        assert not plugin_with_gui.planController.actionNewPlan.isEnabled()

    def test_open_project(self, plugin_with_gui, datadir):
        project = QgsProject.instance()
        project.read(str((datadir / 'test_project.qgs').resolve()))
        assert len(project.mapLayers()) == 3
        assert len(plugin_with_gui.planManager) == 1
        project.clear()

    def test_close_project(self, plugin_with_project):
        QgsProject.instance().clear()
        assert len(plugin_with_project.planManager) == 0
        assert not plugin_with_project.planController.actionNewPlan.isEnabled()

    def test_write_project_calls_storage(self, plugin_with_project: redistricting.Redistricting, mocker: MockerFixture):
        storage = mocker.patch('redistricting.redistricting.ProjectStorage')
        QgsProject.instance().write()
        storage.assert_called_once()

    def test_write_project_no_plan(self, plugin_with_gui, mocker: MockerFixture):  # pylint: disable=unused-argument
        storage = mocker.patch('redistricting.redistricting.ProjectStorage')
        project = QgsProject.instance()
        project.write()
        storage.assert_not_called()
