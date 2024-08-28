"""QGIS Redistricting Plugin - unit tests for RdsFieldTableView class"""
import pytest
from pytestqt.plugin import QtBot
from qgis.PyQt.QtCore import Qt

from redistricting.gui.StatsModel import RdsPlanMetricsModel
from redistricting.models import RdsPlan
from redistricting.services import PlanEditor

# pylint: disable=no-self-use


class TestStatsModel:
    @pytest.fixture
    def stats_model(self, plan: RdsPlan):
        return RdsPlanMetricsModel(plan.metrics)

    def test_model(self, stats_model, qtmodeltester):
        qtmodeltester.check(stats_model)

    def test_rowcount(self, stats_model: RdsPlanMetricsModel):
        assert stats_model.rowCount() == 9

    def test_headerdata(self, stats_model: RdsPlanMetricsModel):
        assert stats_model.headerData(0, Qt.Vertical, Qt.DisplayRole) == 'Population'

    @pytest.mark.parametrize("row,value", [
        (0, '227,036'),
        (1, 'Yes'),
        (3, '0.341'),
        (4, '0.417'),
        (5, '0.811'),
    ])
    def test_data(self, stats_model: RdsPlanMetricsModel, row, value):
        data = stats_model.data(stats_model.createIndex(row, 0), Qt.DisplayRole)
        assert data == value

    # pylint: disable=unused-argument
    def test_signals(self, stats_model: RdsPlanMetricsModel, plan: RdsPlan, mock_taskmanager, qtbot: QtBot):
        with qtbot.waitSignals([stats_model.modelAboutToBeReset, stats_model.modelReset]):
            e = PlanEditor.fromPlan(plan)
            e.appendGeoField('countyid')
            e.updatePlan()
            plan.metrics.updateGeoFields(plan.geoFields)

    def test_clear_stats(self, stats_model: RdsPlanMetricsModel, qtbot: QtBot):
        with qtbot.waitSignals([stats_model.modelAboutToBeReset, stats_model.modelReset]):
            stats_model.setStats(None)
