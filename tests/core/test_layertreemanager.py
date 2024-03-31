
import pytest
from pytest_mock import MockerFixture
from qgis.core import QgsLayerTreeGroup
from qgis.gui import QgisInterface

from redistricting.services.LayerTreeManager import LayerTreeManager

# pylint: disable=unused-argument


class TestLayerTreeManager:
    @pytest.fixture
    def layertree_plan(self, mock_plan, mocker: MockerFixture):
        return mock_plan

    @pytest.fixture
    def manager(self, mocker: MockerFixture):
        mocker.patch("redistricting.services.LayerTreeManager.QgsLayerTreeGroup")
        manager = LayerTreeManager()
        return manager

    def test_create_group(self, manager: LayerTreeManager, layertree_plan):
        group = manager.createGroup(layertree_plan)
        manager.planRoot.addChildNode.assert_called_once_with(group)

    def test_create_group_invalid_plan_raises(self, manager: LayerTreeManager, mocker: MockerFixture, layertree_plan):
        layertree_plan.isValid.return_value = False
        with pytest.raises(ValueError):
            manager.createGroup(layertree_plan)

    def test_plan_from_group(self, manager: LayerTreeManager, layertree_plan):
        group = manager.createGroup(layertree_plan)
        group.customProperty.return_value = str(layertree_plan.id)
        assert manager.planIdFromGroup(group) == layertree_plan.id

    def test_remove_plan(self, manager: LayerTreeManager, layertree_plan, mocker: MockerFixture):
        group = mocker.create_autospec(spec=QgsLayerTreeGroup)
        getGroupForPlan = mocker.patch.object(manager, "getGroupForPlan")
        getGroupForPlan.return_value = group
        manager.removeGroup(layertree_plan)
        manager.planRoot.removeChildNode.assert_called_once()

    def test_remove_plan_not_in_tree_no_action(self, manager: LayerTreeManager, layertree_plan, mocker: MockerFixture):
        getGroupForPlan = mocker.patch.object(manager, "getGroupForPlan")
        getGroupForPlan.return_value = None
        manager.removeGroup(layertree_plan)
        manager.planRoot.removeChildNode.assert_not_called()

    def test_get_plan_groups(self, manager, qgis_new_project, mocker: MockerFixture, qgis_iface: QgisInterface, assign_layer, dist_layer):
        group1 = mocker.create_autospec(QgsLayerTreeGroup)
        group2 = mocker.create_autospec(QgsLayerTreeGroup)
        manager.planRoot.findGroups.return_value = [group1, group2]

        groups = manager.planGroups()
        assert isinstance(groups, list)
        assert len(groups) == 2
        assert group1 in groups
        assert group2 in groups

    def test_get_plan_groups_non_plan_group_ignored(self, manager, qgis_new_project, mocker: MockerFixture, qgis_iface: QgisInterface, assign_layer, dist_layer):
        group1 = mocker.create_autospec(QgsLayerTreeGroup)
        group2 = mocker.create_autospec(QgsLayerTreeGroup)
        group2.customProperty.return_value = None
        manager.planRoot.findGroups.return_value = [group1, group2]

        groups = manager.planGroups()
        assert isinstance(groups, list)
        assert len(groups) == 1
        assert groups[0] == group1
        assert group2 not in groups
