"""QGIS Redistricting Plugin - unit tests for RdsFieldTableView class"""
import pytest
from pytestqt.plugin import QtBot
from qgis.PyQt.QtCore import Qt

from redistricting.gui.StatsModel import StatsModel
from redistricting.models import RdsPlan

# pylint: disable=no-self-use


class TestStatsModel:
    @pytest.fixture
    def stats_model(self, plan: RdsPlan) -> StatsModel:
        return StatsModel(plan.stats)

    def test_model(self, stats_model, qtmodeltester):
        qtmodeltester.check(stats_model)

    def test_rowcount(self, stats_model: StatsModel):
        assert stats_model.rowCount() == 9

    def test_headerdata(self, stats_model: StatsModel):
        assert stats_model.headerData(0, Qt.Vertical, Qt.DisplayRole) == 'Population'

    def test_data(self, stats_model: StatsModel):
        data = stats_model.data(stats_model.createIndex(0, 0), Qt.DisplayRole)
        assert data == '227,036'

    # pylint: disable=unused-argument
    def test_signals(self, stats_model: StatsModel, plan: RdsPlan, qtbot: QtBot):
        with qtbot.waitSignals([stats_model.modelAboutToBeReset, stats_model.modelReset]):
            e = PlanEditor.fromPlan(plan)
            e.appendGeoField('countyid')
            e.updatePlan()
            plan.stats.updateGeoFields(plan.geoFields)

    def test_clear_stats(self, stats_model: StatsModel, qtbot: QtBot):
        with qtbot.waitSignals([stats_model.modelAboutToBeReset, stats_model.modelReset]):
            stats_model.setStats(None)
