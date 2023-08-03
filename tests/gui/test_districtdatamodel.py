"""QGIS Redistricting Plugin - unit tests for RdsFieldTableView class"""
import pytest
from pytestqt.plugin import QtBot
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QBrush

from redistricting.core import (
    DistrictDataModel,
    PlanEditor,
    RedistrictingPlan
)

# pylint: disable=no-self-use


class TestDistrictDataModel:
    @pytest.fixture
    def district_model(self, plan) -> DistrictDataModel:
        return DistrictDataModel(plan)

    def test_model(self, district_model, qtmodeltester):
        qtmodeltester.check(district_model)

    def test_rowcount(self, district_model):
        assert district_model.rowCount() == 3

    def test_colcount(self, district_model):
        assert district_model.columnCount() == 15

    def test_headerdata(self, district_model):
        data = district_model.headerData(14, Qt.Horizontal, Qt.DisplayRole)
        assert data == 'Convex Hull'

    def test_data(self, district_model: DistrictDataModel):
        data = district_model.data(district_model.createIndex(0, 1), Qt.DisplayRole)
        assert data == 'Unassigned'
        data = district_model.data(district_model.createIndex(0, 0), Qt.BackgroundRole)
        assert isinstance(data, QBrush)

    # pylint: disable=protected-access
    def test_headings(self, district_model: DistrictDataModel):
        assert district_model._headings == ['District', 'Name', 'Population',
                                            'Deviation', '%Deviation', 'VAP',
                                            'APBVAP', '%APBVAP', 'WVAP', '%WVAP', 'HVAP', '%HVAP',
                                            'Polsby-Popper', 'Reock', 'Convex Hull']

    def test_column_keys(self, district_model: DistrictDataModel):
        assert district_model._keys == ['district', 'name', 'pop_total',
                                        'deviation', 'pct_deviation', 'vap_total',
                                        'vap_apblack', 'pct_vap_apblack',
                                        'vap_nh_white', 'pct_vap_nh_white',
                                        'vap_hispanic', 'pct_vap_hispanic',
                                        'polsbyPopper', 'reock', 'convexHull']
    # pylint: enable=protected-access

    def test_signals(self, district_model: DistrictDataModel, plan: RedistrictingPlan, qtbot: QtBot):
        with qtbot.waitSignal(district_model.dataChanged):
            e = PlanEditor.fromPlan(plan)
            e.setDeviation(0.01)
            e.updatePlan()

        with qtbot.waitSignals([district_model.modelAboutToBeReset, district_model.modelReset]):
            e = PlanEditor.fromPlan(plan)
            e.removePopField('vap_total')
            e.updatePlan()

        with qtbot.waitSignals([district_model.rowsAboutToBeInserted, district_model.rowsInserted]):
            plan.addDistrict(3, 'District 3')

        with qtbot.waitSignal(district_model.dataChanged):
            district_model.setData(district_model.createIndex(3, 1), 'Council District 3', Qt.EditRole)
        assert plan.districts[3].name == 'Council District 3'

        with qtbot.waitSignals([district_model.rowsAboutToBeRemoved, district_model.rowsRemoved]):
            plan.removeDistrict(3)

        with qtbot.waitSignals([district_model.modelAboutToBeReset, district_model.modelReset]):
            district_model.plan = None
