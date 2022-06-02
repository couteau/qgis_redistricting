"""QGIS Redistricting Plugin - unit tests for DistrictList class"""
import pytest
from redistricting.core.Delta import Delta

from redistricting.core.Plan import RedistrictingPlan

# pylint: disable=no-self-use


class TestDelta:
    @pytest.fixture
    def delta(self, plan: RedistrictingPlan):
        return Delta(plan, plan.districts[1], {
            'pop_total': 100,
            'vap_total': 80,
            'vap_nh_black': 20,
            'vap_apblack': 25,
            'vap_nh_white': 40
        })

    def test_create(self, delta: Delta):
        assert delta.district == 1
