import pandas as pd
import pytest

from redistricting.gui.DeltaListModel import DeltaListModel
from redistricting.models import RdsPlan
from redistricting.models.DeltaList import DeltaList
from redistricting.services import PlanEditor

# pylint: disable=unused-argument,protected-access


class TestDeltaModel:
    @pytest.fixture
    def delta_model(self, plan):
        df = pd.DataFrame.from_records(
            [{
                'district': 1,
                'pop_total': 7,
                'new_pop_total': 95,
                'deviation': 5,
                'pct_deviation': 0.05,
                'vap_total': 5,
                'new_vap_total': 80,
                'vap_apblack': -5,
                'new_vap_apblack': 25,
                'pct_vap_apblack': 0.3125,
                'vap_nh_white': 3,
                'new_vap_nh_white': 40,
                'pct_vap_nh_white': 0.5,
                'vap_hispanic': 0,
                'new_vap_hispanic': 10,
                'pct_vap_hispanic': 0.125
            }],
            index='district'
        )
        delta = DeltaList()
        delta.setData(df)
        model = DeltaListModel()
        model.setDelta(plan, delta)
        model._delta._data = df
        return model

    def test_update_fields(self, delta_model: DeltaListModel, plan: RdsPlan, block_layer):
        assert delta_model.rowCount() == 15
        e = PlanEditor.fromPlan(plan)
        e.appendDataField('vap_nh_black')
        e.updatePlan()
        assert delta_model.rowCount() == 18
