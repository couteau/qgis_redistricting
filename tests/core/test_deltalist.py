"""QGIS Redistricting Plugin - unit tests for DeltaList class"""
import pytest
import pandas as pd
from redistricting.core.DeltaList import DeltaList
from redistricting.core.Field import DataField
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
        assert len(empty_delta_list.fields) == 15

    def test_heading(self, empty_delta_list: DeltaList):
        assert empty_delta_list.heading(3) == '%Deviation'

    def test_update_fields(self, empty_delta_list, plan: RedistrictingPlan, block_layer):
        plan.appendDataField(DataField(block_layer, 'vap_hispanic'))
        empty_delta_list.updateFields()
        assert empty_delta_list.fieldCount() == 18

    def test_update_districts(self, delta_list):
        assert len(delta_list) == 1

    def test_clear(self, delta_list):
        delta_list.clear()
        assert len(delta_list) == 0

    def test_getitem(self, delta_list, plan: RedistrictingPlan):
        assert delta_list[0, 0] == '44,784'
        assert delta_list[1, 0] == '+100'
        assert delta_list[14, 0] == '+70.18%'
        assert delta_list['1'] == plan.districts[1].delta
        assert delta_list[0] == plan.districts[1].delta
