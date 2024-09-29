"""QGIS Redistricting Plugin - unit tests for RdsFieldTableView class"""
import pytest
from pytestqt.plugin import QtBot
from qgis.PyQt.QtCore import Qt

from redistricting.models import RdsPlan
from redistricting.services import (
    PlanEditor,
    RdsPlanMetricsModel
)

# pylint: disable=no-self-use


class TestMetricsModel:
    @pytest.fixture
    def metrics_model(self, plan: RdsPlan):
        return RdsPlanMetricsModel(plan.metrics)

    def test_model(self, metrics_model, qtmodeltester):
        qtmodeltester.check(metrics_model)

    def test_rowcount(self, metrics_model: RdsPlanMetricsModel):
        assert metrics_model.rowCount() == 11

    def test_headerdata(self, metrics_model: RdsPlanMetricsModel):
        assert metrics_model.headerData(0, Qt.Vertical, Qt.DisplayRole) == 'Population'

    @pytest.mark.parametrize("row,value", [
        (0, '227,036'),
        (2, 'Yes'),
        (3, 'Yes'),
        (5, '0.341'),
        (6, '0.417'),
        (7, '0.811'),
    ])
    def test_data(self, metrics_model: RdsPlanMetricsModel, row, value):
        data = metrics_model.data(metrics_model.createIndex(row, 0), Qt.DisplayRole)
        assert data == value

    # pylint: disable=unused-argument
    def test_signals(self, metrics_model: RdsPlanMetricsModel, plan: RdsPlan, mock_taskmanager, qtbot: QtBot):
        with qtbot.waitSignals([metrics_model.modelAboutToBeReset, metrics_model.modelReset]):
            e = PlanEditor.fromPlan(plan)
            e.appendGeoField('countyid')
            e.updatePlan()

    def test_clear_metrics(self, metrics_model: RdsPlanMetricsModel, qtbot: QtBot):
        with qtbot.waitSignals([metrics_model.modelAboutToBeReset, metrics_model.modelReset]):
            metrics_model.setMetrics(None)
