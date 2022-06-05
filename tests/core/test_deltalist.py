"""QGIS Redistricting Plugin - unit tests for DeltaList class"""
import pytest
import pandas as pd
from redistricting.core.DeltaList import DeltaList
from redistricting.core.Plan import RedistrictingPlan

# pylint: disable=no-self-use


class TestDeltaList:
    @pytest.fixture
    def empty_delta_list(self, plan: RedistrictingPlan) -> DeltaList:
        return DeltaList(plan)

    @pytest.fixture
    def delta_list(self, empty_delta_list):
        df = pd.DataFrame.from_records(
            [{
                'district': 1,
                'pop_total': 100,
                'vap_total': 80,
                'vap_nh_black': 20,
                'vap_apblack': 25,
                'vap_nh_white': 40
            }],
            index='district'
        )
        empty_delta_list.updateDistricts(df)
        return empty_delta_list

    def test_create(self, empty_delta_list: DeltaList):
        assert len(empty_delta_list) == 0

    def test_clear(self, delta_list):
        delta_list.clear()
        assert len(delta_list) == 0

    def test_getitem(self, delta_list, plan: RedistrictingPlan):
        assert delta_list['1'] == plan.districts[1].delta
        assert delta_list[0] == plan.districts[1].delta
