"""QGIS Redistricting Plugin - unit tests for RdsFieldTableView class"""
import pytest
from pytestqt.plugin import QtBot
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QBrush

from redistricting.gui import DistrictDataModel
from redistricting.models import RedistrictingPlan
from redistricting.services import PlanEditor

# pylint: disable=no-self-use


class TestDistrictDataModel:
    @pytest.fixture
    def district_model(self, plan) -> DistrictDataModel:
        return DistrictDataModel(plan)

    def test_model(self, district_model, qtmodeltester):
        qtmodeltester.check(district_model)

    def test_rowcount(self, district_model):
        assert district_model.rowCount() == 6

    def test_colcount(self, district_model):
        assert district_model.columnCount() == 16

    def test_headerdata(self, district_model):
        assert district_model.headerData(0, Qt.Horizontal, Qt.DisplayRole) == 'District'
        assert district_model.headerData(15, Qt.Horizontal, Qt.DisplayRole) == 'Convex Hull'

    def test_data(self, district_model: DistrictDataModel):
        data = district_model.data(district_model.createIndex(0, 1), Qt.DisplayRole)
        assert data == 'Unassigned'
        data = district_model.data(district_model.createIndex(0, 0), Qt.BackgroundRole)
        assert isinstance(data, QBrush)

    def test_signals(self, district_model: DistrictDataModel, plan: RedistrictingPlan, qtbot: QtBot):
        with qtbot.waitSignal(district_model.dataChanged):
            e = PlanEditor.fromPlan(plan)
            e.setDeviation(0.01)
            e.updatePlan()

        with qtbot.waitSignals([district_model.modelAboutToBeReset, district_model.modelReset]):
            e = PlanEditor.fromPlan(plan)
            e.removePopField('vap_total')
            e.updatePlan()

        with qtbot.waitSignal(district_model.dataChanged):
            district_model.setData(district_model.createIndex(3, 1), 'Council District 3', Qt.EditRole)
        assert plan.districts[3].name == 'Council District 3'

    def test_clear_plan(self, district_model: DistrictDataModel, qtbot: QtBot):
        with qtbot.waitSignals([district_model.modelAboutToBeReset, district_model.modelReset]):
            district_model.plan = None
