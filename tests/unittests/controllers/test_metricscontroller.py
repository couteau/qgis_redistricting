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
import pytest
from pytest_mock import MockerFixture
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import pyqtBoundSignal
from qgis.PyQt.QtWidgets import QAction

from redistricting.controllers import MetricsController
from redistricting.gui import DlgSplitDetail
from redistricting.models import RdsGeoField


class TestMetricsController:
    @pytest.fixture
    def controller(self, qgis_iface, mock_planmanager, mock_project, mock_toolbar, mock_updater):
        return MetricsController(qgis_iface, mock_project, mock_planmanager, mock_toolbar, mock_updater)

    @pytest.fixture
    def controller_with_active_plan(self, qgis_iface: QgisInterface, mock_planmanager_with_active_plan, mock_project, mock_toolbar, mock_updater):
        controller = MetricsController(qgis_iface, mock_project,
                                       mock_planmanager_with_active_plan, mock_toolbar, mock_updater)
        controller.load()
        return controller

    def test_create(self, controller):
        assert controller
        assert isinstance(controller.actionShowSplitsDialog, QAction)

    def test_load(self, controller, mock_planmanager):
        controller.load()
        mock_planmanager.activePlanChanged.connect.assert_called_once_with(controller.planChanged)

    def test_unload(self, controller, mock_planmanager):
        controller.load()
        controller.unload()
        mock_planmanager.activePlanChanged.disconnect.assert_called_once_with(controller.planChanged)

    def test_plan_changed(self, controller_with_active_plan: MetricsController, mock_plan, mocker: MockerFixture):
        controller_with_active_plan.dlgSplits = mocker.MagicMock()
        assert not controller_with_active_plan.actionShowSplitsDialog.isEnabled()
        controller_with_active_plan.planChanged(mock_plan)
        assert controller_with_active_plan.actionShowSplitsDialog.isEnabled()
        assert controller_with_active_plan.dlgSplits is None

    def test_plan_changed_none_disables_action(self, controller_with_active_plan: MetricsController, mock_plan, mocker: MockerFixture):
        controller_with_active_plan.dlgSplits = mocker.MagicMock()
        controller_with_active_plan.planChanged(mock_plan)
        assert controller_with_active_plan.actionShowSplitsDialog.isEnabled()
        controller_with_active_plan.planChanged(None)
        assert not controller_with_active_plan.actionShowSplitsDialog.isEnabled()
        assert controller_with_active_plan.dlgSplits is None

    def test_show_splits_dialog(self, controller_with_active_plan: MetricsController, mock_plan, qgis_iface, mocker: MockerFixture):
        dlgClass = mocker.patch("redistricting.controllers.metrics.DlgSplitDetail", autospec=DlgSplitDetail)
        dlgClass.return_value.geographyChanged = mocker.PropertyMock(spec=pyqtBoundSignal)
        dlgClass.return_value.destroyed = mocker.PropertyMock(spec=pyqtBoundSignal)
        dlgClass.return_value.cmbGeography = mocker.MagicMock()
        field = mocker.create_autospec(spec=RdsGeoField)
        controller_with_active_plan.showSplits(field)
        dlgClass.assert_called_once_with(mock_plan, qgis_iface.mainWindow())

    def test_show_splits_dialog_no_geofield_returns(self, controller_with_active_plan: MetricsController, mocker: MockerFixture):
        dlgClass = mocker.patch("redistricting.controllers.metrics.DlgSplitDetail", autospec=DlgSplitDetail)
        sender = mocker.patch.object(controller_with_active_plan, "sender")
        sender.return_value = controller_with_active_plan.actionShowSplitsDialog
        controller_with_active_plan.showSplits()
        dlgClass.assert_not_called()

    def test_show_splits_dialog_geofield_on_sender_runs_dialog(self, controller_with_active_plan: MetricsController, mock_plan, qgis_iface, mocker: MockerFixture):
        dlgClass = mocker.patch("redistricting.controllers.metrics.DlgSplitDetail", autospec=DlgSplitDetail)
        dlgClass.return_value.geographyChanged = mocker.PropertyMock(spec=pyqtBoundSignal)
        dlgClass.return_value.destroyed = mocker.PropertyMock(spec=pyqtBoundSignal)
        dlgClass.return_value.cmbGeography = mocker.MagicMock()
        field = mocker.create_autospec(spec=RdsGeoField)
        controller_with_active_plan.actionShowSplitsDialog.setData(field)
        sender = mocker.patch.object(controller_with_active_plan, "sender")
        sender.return_value = controller_with_active_plan.actionShowSplitsDialog
        controller_with_active_plan.showSplits()
        dlgClass.assert_called_once_with(mock_plan, qgis_iface.mainWindow())

    def test_show_splits_dialog_existing_dialog(self, controller_with_active_plan: MetricsController, mocker: MockerFixture):
        dlgClass = mocker.patch("redistricting.controllers.metrics.DlgSplitDetail", autospec=DlgSplitDetail)
        dlgClass.return_value.geographyChanged = mocker.PropertyMock(spec=pyqtBoundSignal)
        dlgClass.return_value.destroyed = mocker.PropertyMock(spec=pyqtBoundSignal)
        dlgClass.return_value.cmbGeography = mocker.MagicMock()
        field = mocker.create_autospec(spec=RdsGeoField)
        controller_with_active_plan.dlgSplits = dlgClass.return_value
        field = mocker.create_autospec(spec=RdsGeoField)
        controller_with_active_plan.showSplits(field)
        dlgClass.assert_not_called()
        dlgClass.return_value.show.assert_called_once()
