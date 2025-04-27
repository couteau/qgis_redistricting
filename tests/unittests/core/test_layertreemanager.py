"""QGIS Redistricting Plugin - unit tests

Copyright 2022-2024, Stuart C. Naifeh

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 *   This program is distributed in the hope that it will be useful, but   *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the          *
 *   GNU General Public License for more details. You should have          *
 *   received a copy of the GNU General Public License along with this     *
 *   program. If not, see <http://www.gnu.org/licenses/>.                  *
 *                                                                         *
 ***************************************************************************/
"""
import pytest
from pytest_mock import MockerFixture
from qgis.core import (
    QgsLayerTreeGroup,
    QgsProject
)
from qgis.gui import QgisInterface

from redistricting.services.layertree import LayerTreeManager

# pylint: disable=unused-argument


class TestLayerTreeManager:
    @pytest.fixture
    def layertree_plan(self, mock_plan, mocker: MockerFixture):
        return mock_plan

    @pytest.fixture
    def manager(self, mocker: MockerFixture):
        mocker.patch("redistricting.services.layertree.QgsLayerTreeGroup")
        project = mocker.create_autospec(spec=QgsProject)
        manager = LayerTreeManager(project)
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
