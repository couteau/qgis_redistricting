import pytest
from qgis.gui import QgisInterface
from qgis.PyQt.QtWidgets import QAction

from redistricting.controllers import (
    ContextMenuController,
    PlanController
)


class TestContextMenuController:
    @pytest.fixture
    def mock_plancontroller(self, mocker):
        kls = mocker.create_autospec(spec=PlanController)
        return kls.return_value

    @pytest.fixture
    def controller(self, qgis_iface, mock_planmanager, mock_project, mock_toolbar, mock_plancontroller):
        return ContextMenuController(qgis_iface, mock_project, mock_planmanager, mock_toolbar, mock_plancontroller)

    @pytest.fixture
    def controller_with_active_plan(self, qgis_iface: QgisInterface, mock_planmanager_with_active_plan, mock_project, mock_toolbar, mock_plancontroller):
        return ContextMenuController(qgis_iface, mock_project, mock_planmanager_with_active_plan, mock_toolbar, mock_plancontroller)

    def test_create(self, controller: ContextMenuController):
        assert controller.contextMenu is not None
        assert controller.contextAction is not None

    def test_load(self, controller: ContextMenuController, qgis_iface: QgisInterface):
        controller.load()
        qgis_iface.addCustomActionForLayerType.assert_called()

    def test_unload(self, controller: ContextMenuController, qgis_iface: QgisInterface):
        controller.unload()
        qgis_iface.removeCustomActionForLayerType.assert_called()

    def test_activate_plan(self, controller_with_active_plan: ContextMenuController, qgis_iface: QgisInterface, mock_planmanager_with_active_plan):
        controller_with_active_plan.contextMenuActivatePlan()
        qgis_iface.layerTreeView.assert_called_once()
        mock_planmanager_with_active_plan.setActivePlan.assert_called_once()

    def test_plan_added(self, controller, mock_plan, qgis_iface: QgisInterface):
        controller.planAdded(mock_plan)
        qgis_iface.addCustomActionForLayer.assert_called()

    def test_context_menu_slot(self, controller_with_active_plan: ContextMenuController, qgis_iface: QgisInterface, mock_planmanager_with_active_plan, mocker):
        action = mocker.create_autospec(spec=QAction)
        trigger = controller_with_active_plan.contextMenuSlot(action)
        trigger()
        action.assert_called_once()
        qgis_iface.layerTreeView.assert_called_once()
        mock_planmanager_with_active_plan.get.assert_called_once()
