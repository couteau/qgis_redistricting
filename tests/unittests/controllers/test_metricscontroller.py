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
from qgis.PyQt.QtCore import QModelIndex, pyqtBoundSignal
from qgis.PyQt.QtWidgets import QAction

from redistricting.controllers import MetricsController
from redistricting.gui import RdsMetricGuiHandler
from redistricting.models import RdsMetric, RdsMetricsModel


class TestMetricsController:
    @pytest.fixture
    def controller(self, qgis_iface, mock_planmanager, mock_project, mock_toolbar, mock_updater):
        return MetricsController(qgis_iface, mock_project, mock_planmanager, mock_toolbar, mock_updater)

    @pytest.fixture
    def controller_with_active_plan(
        self, qgis_iface: QgisInterface, mock_planmanager_with_active_plan, mock_project, mock_toolbar, mock_updater
    ):
        controller = MetricsController(
            qgis_iface, mock_project, mock_planmanager_with_active_plan, mock_toolbar, mock_updater
        )
        controller.load()
        return controller

    def test_create(self, controller):
        assert controller
        assert controller.metricsModel is not None
        assert controller.handler_cache is not None
        assert len(controller.handler_cache) == 0
        assert isinstance(controller.actionCopyMetrics, QAction)

    def test_load(self, controller, mock_planmanager):
        controller.load()
        assert controller.metricsModel is not None
        assert controller.dockwidget is not None
        mock_planmanager.activePlanChanged.connect.assert_called_once_with(controller.planChanged)

    def test_unload(self, controller, mock_planmanager):
        controller.load()
        controller.unload()
        mock_planmanager.activePlanChanged.disconnect.assert_called_once_with(controller.planChanged)

    def test_plan_changed(self, controller_with_active_plan: MetricsController, mock_plan, mocker: MockerFixture):
        handler = mocker.MagicMock()
        controller_with_active_plan.handler_cache["test"] = handler
        controller_with_active_plan.planChanged(mock_plan)
        handler.update.assert_called_once_with(mock_plan)
        controller_with_active_plan.planChanged(None)
        handler.deactivate.assert_called_once()
        assert len(controller_with_active_plan.handler_cache) == 0

    def test_show_metric_detail_creates_handler(
        self, controller_with_active_plan: MetricsController, mocker: MockerFixture
    ):
        get_metric_handler = mocker.patch("redistricting.controllers.metrics.get_metric_handler")
        handler = mocker.create_autospec(spec=RdsMetricGuiHandler)
        handler.deactivated = mocker.create_autospec(spec=pyqtBoundSignal)
        get_metric_handler.return_value = handler
        mocker.patch.object(controller_with_active_plan, "metricsModel", spec=RdsMetricsModel)
        metric = mocker.create_autospec(spec=RdsMetric)
        controller_with_active_plan.metricsModel.metric.return_value = metric
        controller_with_active_plan.metricsModel.metricKey.return_value = None
        index = mocker.create_autospec(spec=QModelIndex)
        assert len(controller_with_active_plan.handler_cache) == 0
        controller_with_active_plan.showMetricsDetail(index)
        assert len(controller_with_active_plan.handler_cache) == 1
        assert list(controller_with_active_plan.handler_cache.values())[0] == handler
        get_metric_handler.assert_called_once()
        get_metric_handler.reset_mock()
        controller_with_active_plan.showMetricsDetail(index)
        assert len(controller_with_active_plan.handler_cache) == 1
        get_metric_handler.assert_not_called()

    def test_show_detail_for_metric_with_no_handler_creates_no_handler(
        self, controller_with_active_plan: MetricsController, mocker: MockerFixture
    ):
        get_metric_handler = mocker.patch("redistricting.controllers.metrics.get_metric_handler")
        get_metric_handler.return_value = None
        metric = mocker.create_autospec(spec=RdsMetric)
        mocker.patch.object(controller_with_active_plan, "metricsModel", spec=RdsMetricsModel)
        controller_with_active_plan.metricsModel.metric.return_value = metric
        controller_with_active_plan.metricsModel.metricKey.return_value = None
        index = mocker.create_autospec(spec=QModelIndex)
        assert len(controller_with_active_plan.handler_cache) == 0
        controller_with_active_plan.showMetricsDetail(index)
        assert len(controller_with_active_plan.handler_cache) == 0

    def test_show_update_handler_calls_update(
        self, controller_with_active_plan: MetricsController, mock_plan, mocker: MockerFixture
    ):
        sender = mocker.patch.object(controller_with_active_plan, "sender")
        sender.return_value = mock_plan
        metric = mocker.create_autospec(spec=RdsMetric)
        mock_plan.metrics.metrics.__iter__.return_value = [metric]
        handler = mocker.create_autospec(spec=RdsMetricGuiHandler)
        controller_with_active_plan.handler_cache[type(metric)] = handler
        controller_with_active_plan.updateMetricsDetail()
        handler.update.assert_called_once_with(mock_plan, metric)
