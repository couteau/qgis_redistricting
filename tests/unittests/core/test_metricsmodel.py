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
from pytestqt.plugin import QtBot
from qgis.PyQt.QtCore import Qt

from redistricting.models import RdsMetricsModel, RdsPlan
from redistricting.models.metricslist import MetricTriggers
from redistricting.services.metrics import MetricsService, MetricsUpdate


class TestMetricsModel:
    @pytest.fixture
    def metrics_model(self, plan: RdsPlan):
        return RdsMetricsModel(plan)

    def test_model(self, metrics_model, qtmodeltester):
        qtmodeltester.check(metrics_model)

    def test_rowcount(self, metrics_model: RdsMetricsModel):
        assert metrics_model.rowCount() == 11

    def test_headerdata(self, metrics_model: RdsMetricsModel):
        headers = [
            metrics_model.headerData(r, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole)
            for r in range(metrics_model.rowCount())
        ]
        assert headers == [
            "Population",
            "%Deviation",
            "Compactness",
            "    Cut Edges",
            "    Polsby-Popper (Mean, Min., Max.)",
            "    Reock (Mean, Min., Max.)",
            "    Convex Hull (Mean, Min., Max.)",
            "Contiguity",
            "Complete",
            "Splits",
            "    VTD",
        ]

    @pytest.mark.parametrize(
        ("row", "value"),
        [
            (0, "227,036"),
            (1, ""),
            (2, None),
            (3, None),
            (4, "0.400, 0.150, 0.800"),
            (5, "0.500, 0.100, 0.900"),
            (6, "0.500, 0.100, 0.900"),
            (7, "YES"),
            (8, "YES"),
            (9, None),
            (10, ""),
        ],
    )
    def test_data(self, metrics_model: RdsMetricsModel, row, value):
        data = metrics_model.data(metrics_model.createIndex(row, 0), Qt.ItemDataRole.DisplayRole)
        assert data == value

    # pylint: disable=unused-argument
    def test_signals(self, metrics_model: RdsMetricsModel, plan: RdsPlan, mock_taskmanager, qtbot: QtBot):
        service = MetricsService()
        with qtbot.waitSignals([metrics_model.modelAboutToBeReset, metrics_model.modelReset]):
            update = MetricsUpdate(MetricTriggers.ON_UPDATE_DEMOGRAPHICS, None, None, None)
            service.finished(MetricsService.UpdateStatus.SUCCESS, None, plan, update, None)

    def test_clear_metrics(self, metrics_model: RdsMetricsModel, qtbot: QtBot):
        with qtbot.waitSignals([metrics_model.modelAboutToBeReset, metrics_model.modelReset]):
            metrics_model.setPlan(None)

        assert metrics_model.rowCount() == 0
