import pandas as pd
import pytest
from qgis.core import QgsProject
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QToolBar

from redistricting.controllers import PendingChangesController
from redistricting.gui import DockPendingChanges
from redistricting.models import (
    DeltaList,
    RdsPlan
)
from redistricting.services import (
    DeltaListModel,
    DeltaUpdateService,
    PlanManager
)
from redistricting.services.DeltaUpdate import DeltaUpdate

# pylint: disable=unused-argument, protected-access


class TestPendingChangesController:
    @pytest.fixture
    def delta(self, plan: RdsPlan, delta_update_service: DeltaUpdateService):
        df = pd.DataFrame.from_records(
            [
                {
                    'district': 1,
                    'pop_total': 7,
                    'new_pop_total': 105,
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
                },
                {
                    'district': 2,
                    'pop_total': -7,
                    'new_pop_total': 80,
                    'deviation': -20,
                    'pct_deviation': -0.20,
                    'vap_total': -5,
                    'new_vap_total': 60,
                    'vap_apblack': 5,
                    'new_vap_apblack': 30,
                    'pct_vap_apblack': 0.5,
                    'vap_nh_white': 3,
                    'new_vap_nh_white': 21,
                    'pct_vap_nh_white': 0.35,
                    'vap_hispanic': 0,
                    'new_vap_hispanic': 10,
                    'pct_vap_hispanic': 0.125
                }
            ],
            index='district'
        )
        delta = DeltaList()
        delta.setData(df)
        delta_update_service._deltas[plan] = DeltaUpdate(plan, None, None, delta, None)
        return delta

    @pytest.fixture
    def controller(self, qgis_iface: QgisInterface, planmanager: PlanManager, toolbar: QToolBar, delta_update_service: DeltaUpdateService):
        return PendingChangesController(qgis_iface, QgsProject.instance(), planmanager, toolbar, delta_update_service)

    @pytest.fixture
    def controller_with_active_plan(self, controller: PendingChangesController, planmanager, plan):
        controller.load()
        planmanager.appendPlan(plan, True)
        return controller

    def test_create(self, controller: PendingChangesController):
        assert isinstance(controller.model, DeltaListModel)

    def test_load(self, controller: PendingChangesController):
        controller.load()
        assert isinstance(controller.dockwidget, DockPendingChanges)

    def test_dockwidget_action(self, controller: PendingChangesController, toolbar: QToolBar):
        controller.load()
        assert controller.actionToggle in toolbar.actions()

        controller.actionToggle.trigger()
        assert controller.dockwidget.isVisible()
        controller.actionToggle.trigger()
        assert not controller.dockwidget.isVisible()

    def test_unload(self, controller: PendingChangesController):
        controller.load()
        controller.unload()
        assert controller.dockwidget is None

    def test_addplan(self, controller: PendingChangesController, planmanager: PlanManager, plan: RdsPlan):
        controller.load()
        assert controller.dockwidget.plan is None
        planmanager.appendPlan(plan, True)
        assert controller.dockwidget.plan == plan
        assert controller.model._delta is None

    def test_addplan_with_delta(self, controller: PendingChangesController, planmanager: PlanManager, plan, delta: DeltaList):
        controller.load()
        planmanager.appendPlan(plan, True)
        assert controller.model._delta is delta

    def test_update_delta_updates_model(self, controller_with_active_plan: PendingChangesController, plan: RdsPlan, delta_update_service: DeltaUpdateService, qtbot):
        assert controller_with_active_plan.model._delta is None
        delta_update_service.watchPlan(plan)
        with qtbot.waitSignal(delta_update_service.updateCompleted, timeout=20000):
            plan.assignLayer.startEditing()
            plan.assignLayer.changeAttributeValue(114, 2, 1, 5)
            # delta_update_service.updatePendingData(plan)

        assert controller_with_active_plan.model._delta is not None
        assert controller_with_active_plan.model.data(
            controller_with_active_plan.model.createIndex(0, 1), Qt.DisplayRole) == '+600'
        plan.assignLayer.rollBack(True)
