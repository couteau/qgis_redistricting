"""Test redististricting plugin initialization"""
import configparser
import pathlib

import pytest
from pytest_mock.plugin import MockerFixture
from pytestqt.plugin import QtBot
from qgis.core import QgsProject

from redistricting import (
    classFactory,
    redistricting
)
from redistricting.models import RedistrictingPlan

# pylint: disable=unused-argument


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
    def plugin_with_plan(self, plugin_with_gui, mock_plan):
        plugin_with_gui.redistrictingPlans.append(mock_plan)
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
        plan: RedistrictingPlan = plugin_with_gui.activePlan
        assert plan.totalPopulation > 0 or plan.districts._needUpdate  # pylint: disable=protected-access
        project.clear()

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
