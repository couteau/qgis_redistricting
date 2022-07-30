"""QGIS Redistricting Plugin - unit tests for DeltaList class"""
import pytest
import pandas as pd
from qgis.PyQt.QtCore import Qt
from redistricting.core.DeltaListModel import DeltaListModel
from redistricting.core import RedistrictingPlan, DataField, PlanEditor

# pylint: disable=no-self-use


class TestDeltaModel:
    @pytest.fixture
    def empty_model(self, plan):
        return DeltaListModel(plan)

    @pytest.fixture
    def delta_model(self, plan):
        df = pd.DataFrame.from_records(
            [{
                'district': 1,
                'pop_total': 100,
                'vap_total': 80,
                'vap_apblack': 25,
                'vap_nh_white': 40,
                'vap_hispanic': 10,
            }],
            index='district'
        )
        model = DeltaListModel(plan)
        model._delta.updateDistricts(df)  # pylint: disable=protected-access
        return model

    def test_create(self, empty_model: DeltaListModel):
        assert empty_model.rowCount() == 15

    def test_model(self, delta_model, empty_model, qtmodeltester):
        qtmodeltester.check(delta_model)
        qtmodeltester.check(empty_model)

    def test_heading(self, delta_model: DeltaListModel):
        assert delta_model.headerData(3, Qt.Vertical, Qt.DisplayRole) == '%Deviation'

    def test_update_fields(self, empty_model, plan: RedistrictingPlan, block_layer):
        e = PlanEditor.fromPlan(plan)
        e.appendDataField(DataField(block_layer, 'vap_nh_black'))
        e.updatePlan()
        assert empty_model.rowCount() == 18

    def test_update_districts(self, delta_model):
        assert delta_model.columnCount() == 1

    def test_data(self, delta_model):
        assert delta_model.data(delta_model.createIndex(0, 0), Qt.DisplayRole) == '44,784'
        assert delta_model.data(delta_model.createIndex(1, 0), Qt.DisplayRole) == '+100'
        assert delta_model.data(delta_model.createIndex(14, 0), Qt.DisplayRole) == '4.32%'
