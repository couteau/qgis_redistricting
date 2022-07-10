"""QGIS Redistricting Plugin - unit tests for PlanGroup class"""
from redistricting.core.PlanGroup import PlanGroup


class TestGroup:
    def test_create(self, plan):
        g = PlanGroup(plan)
        assert g.groupName == 'Redistricting Plan - ' + plan.name
