from typing import Iterable
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from redistricting.models.Plan import RedistrictingPlan
from redistricting.services.PlanManager import PlanManager


class TestPlanManager:
    @pytest.fixture
    def mock_plan(self, mocker: MockerFixture):
        plan = mocker.create_autospec(spec=RedistrictingPlan)
        plan.id = uuid4()
        return plan

    @pytest.fixture
    def planmanager(self, mocker: MockerFixture, mock_plan):
        p = PlanManager()
        plan1 = mocker.create_autospec(spec=RedistrictingPlan)
        plan2 = mocker.create_autospec(spec=RedistrictingPlan)
        p.appendPlan(plan1, makeActive=False)
        p.appendPlan(plan2, makeActive=False)
        p.appendPlan(mock_plan, makeActive=False)
        return p

    def test_setactiveplan(self, planmanager, mock_plan):
        assert planmanager.activePlan is None
        planmanager.setActivePlan(mock_plan)
        assert planmanager.activePlan == mock_plan

    def test_set_active_plan_uuid(self, planmanager, mock_plan):
        assert planmanager.activePlan is None
        planmanager.setActivePlan(mock_plan.id)
        assert planmanager.activePlan == mock_plan

    def test_set_active_plan_uuid_not_in_list(self, planmanager):
        assert planmanager.activePlan is None
        planmanager.setActivePlan(uuid4())
        assert planmanager.activePlan is None

    def test_set_active_plan_none(self, planmanager, mock_plan):
        planmanager.setActivePlan(mock_plan)
        assert planmanager.activePlan is not None
        planmanager.setActivePlan(None)
        assert planmanager.activePlan is None

    def test_set_active_invalid_plan(self, planmanager, mock_plan):
        mock_plan.isValid.return_value = False
        planmanager.setActivePlan(mock_plan)
        assert planmanager.activePlan is None

    def test_append_with_makeactive_true_activates_plan(self, planmanager, mocker: MockerFixture):
        assert len(planmanager) == 3
        assert planmanager.activePlan is None
        plan = mocker.create_autospec(spec=RedistrictingPlan)
        planmanager.appendPlan(plan, makeActive=True)
        assert len(planmanager) == 4
        assert planmanager.activePlan == plan

    def test_append_with_makeactive_false_does_not_activate_plan(self, planmanager, mocker: MockerFixture):
        assert len(planmanager) == 3
        assert planmanager.activePlan is None
        plan = mocker.create_autospec(spec=RedistrictingPlan)
        planmanager.appendPlan(plan, makeActive=False)
        assert len(planmanager) == 4
        assert planmanager.activePlan is None

    def test_extend(self, mocker: MockerFixture):
        p = PlanManager()
        assert len(p) == 0
        plan1 = mocker.create_autospec(spec=RedistrictingPlan)
        plan2 = mocker.create_autospec(spec=RedistrictingPlan)
        p.extend([plan1, plan2])
        assert len(p) == 2

    def test_remove(self, planmanager, mock_plan):
        planmanager.setActivePlan(mock_plan)
        assert planmanager.activePlan == mock_plan
        planmanager.removePlan(mock_plan)
        assert len(planmanager) == 2
        assert planmanager.activePlan is None

    def test_clear(self, planmanager, mock_plan):
        planmanager.setActivePlan(mock_plan)
        assert planmanager.activePlan == mock_plan
        planmanager.clear()
        assert len(planmanager) == 0
        assert planmanager.activePlan is None

    def test_signals(self, planmanager, mock_plan, qtbot):
        with qtbot.wait_signal(planmanager.activePlanChanged):
            planmanager.setActivePlan(mock_plan)

    def test_iterable(self, planmanager):
        assert isinstance(planmanager, Iterable)

    def test_planbyid_given_valid_id_returns_plan(self, planmanager, mock_plan):
        assert planmanager[mock_plan.id] == mock_plan

    def test_planbyid_given_invalid_id_returns_none(self, planmanager):
        with pytest.raises(KeyError):
            planmanager[uuid4()]  # pylint: disable=pointless-statement, expression-not-assigned
        assert planmanager.get(uuid4()) is None