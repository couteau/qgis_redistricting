"""QGIS Redistricting Plugin - test plugin factory/initialization

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
from typing import Generator

import pytest
from pytest_lazy_fixtures import lf
from pytest_mock.plugin import MockerFixture
from pytestqt.plugin import QtBot
from qgis.core import QgsProject
from qgis.gui import QgisInterface
from qgis.PyQt.QtWidgets import QMessageBox

from redistricting import (
    classFactory,
    redistricting
)

# pylint: disable=unused-argument


class TestPluginInit:

    @pytest.fixture
    def plugin(self, qgis_iface: QgisInterface, tmp_path, mocker: MockerFixture) -> redistricting.Redistricting:
        settings = mocker.patch('redistricting.redistricting.QSettings')
        settings_obj = settings.return_value
        settings_obj.value.return_value = 'en_US'

        QgsProject.instance().setFileName(str(tmp_path / "test.qgz"))

        return classFactory(qgis_iface)

    @pytest.fixture
    def plugin_with_gui(self, plugin: redistricting.Redistricting) -> Generator[redistricting.Redistricting, None, None]:
        plugin.initGui()
        yield plugin
        plugin.unload()

    @pytest.fixture
    def plugin_with_plan(self, plugin_with_gui: redistricting.Redistricting, plan) -> redistricting.Redistricting:
        plugin_with_gui.planManager.appendPlan(plan)
        return plugin_with_gui

    @pytest.fixture
    def plugin_with_project(self, plugin_with_gui, datadir, qtbot: QtBot, mocker: MockerFixture, qgis_new_project):  # pylint: disable=unused-argument
        dlg = mocker.patch('redistricting.redistricting.QMessageBox')
        dlg.return_value.warning.return_value = QMessageBox.StandardButton.Ok
        project = QgsProject.instance()
        with qtbot.waitSignal(project.readProject):
            project.read(str((datadir / 'test_project.qgz').resolve()))
        yield plugin_with_gui
        project.clear()

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

    def test_open_project(self, plugin_with_gui, datadir, mocker: MockerFixture):
        dlg = mocker.patch('redistricting.redistricting.QMessageBox')
        dlg.return_value.warning.return_value = QMessageBox.StandardButton.Ok
        project = QgsProject.instance()
        project.read(str((datadir / 'test_project.qgz').resolve()))
        assert len(project.mapLayers()) == 9
        assert len(plugin_with_gui.planManager) == 1
        project.clear()

    def test_close_project(self, plugin_with_project):
        QgsProject.instance().clear()
        assert len(plugin_with_project.planManager) == 0
        assert not plugin_with_project.planController.actionNewPlan.isEnabled()

    def test_write_project_calls_storage(self, plugin_with_project: redistricting.Redistricting, datadir, mocker: MockerFixture):
        dlg = mocker.patch('redistricting.redistricting.QMessageBox')
        dlg.return_value.warning.return_value = QMessageBox.StandardButton.Ok
        storage = mocker.patch('redistricting.redistricting.ProjectStorage')
        QgsProject.instance().write()
        storage.assert_called_once()
        QgsProject.instance().clear()

    def test_write_project_no_plan(self, plugin_with_gui, mocker: MockerFixture):  # pylint: disable=unused-argument
        storage = mocker.patch('redistricting.redistricting.ProjectStorage')
        QgsProject.instance().write()
        storage.assert_not_called()
