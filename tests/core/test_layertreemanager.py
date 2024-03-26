from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from qgis.core import (
    QgsLayerTreeGroup,
    QgsProject
)
from qgis.gui import QgisInterface

from redistricting.models.Plan import RedistrictingPlan
from redistricting.services.LayerTreeManager import LayerTreeManager

# pylint: disable=unused-argument


class TestLayerTreeManager:
    @pytest.fixture
    def mock_plan(self, mocker: MockerFixture, assign_layer, dist_layer):
        plan = mocker.create_autospec(spec=RedistrictingPlan, instance=True)
        plan.name = "Test"
        plan.id = uuid4()
        plan.assignLayer = assign_layer
        plan.distLayer = dist_layer
        return plan

    def test_addplan(self, qgis_new_project, mock_plan):
        project = QgsProject.instance()
        manager = LayerTreeManager()
        manager.createGroup(mock_plan)
        assert project.layerTreeRoot().findGroup(mock_plan.name)

    def test_plan_from_group(self, qgis_new_project, qgis_iface: QgisInterface, mock_plan):
        manager = LayerTreeManager()
        manager.createGroup(mock_plan)

        group = qgis_iface.layerTreeView().currentGroupNode()
        assert manager.planIdFromGroup(group) == mock_plan.id

    def test_remove_plan(self, qgis_new_project, mock_plan):
        project = QgsProject.instance()
        manager = LayerTreeManager()
        manager.createGroup(mock_plan)
        assert project.layerTreeRoot().findGroup(mock_plan.name) is not None
        manager.removeGroup(mock_plan)
        assert project.layerTreeRoot().findGroup(mock_plan.name) is None

    def test_bring_plan_to_top(self, qgis_new_project, mocker: MockerFixture, qgis_iface: QgisInterface, block_layer, assign_layer, dist_layer):
        project = QgsProject.instance()
        project.addMapLayer(block_layer, True)
        manager = LayerTreeManager()

        plan1 = mocker.create_autospec(spec=RedistrictingPlan, instance=True)
        plan1.name = "Test1"
        plan1.id = uuid4()
        plan1.assignLayer = assign_layer
        plan1.distLayer = dist_layer
        manager.createGroup(plan1)
        plan2 = mocker.create_autospec(spec=RedistrictingPlan, instance=True)
        plan2.name = "Test2"
        plan2.id = uuid4()
        plan2.assignLayer = assign_layer
        plan2.distLayer = dist_layer
        manager.createGroup(plan2)

        qgis_iface.setActiveLayer(block_layer)
        manager.bringPlanToTop(plan2)
        assert project.layerTreeRoot().hasCustomLayerOrder()

    def test_get_plan_groups(self, qgis_new_project, mocker: MockerFixture, qgis_iface: QgisInterface, assign_layer, dist_layer):
        manager = LayerTreeManager()
        plan1 = mocker.create_autospec(spec=RedistrictingPlan, instance=True)
        plan1.name = "Test"
        plan1.id = uuid4()
        plan1.assignLayer = assign_layer
        plan1.distLayer = dist_layer
        manager.createGroup(plan1)
        plan2 = mocker.create_autospec(spec=RedistrictingPlan, instance=True)
        plan2.name = "Test"
        plan2.id = uuid4()
        plan2.assignLayer = assign_layer
        plan2.distLayer = dist_layer
        manager.createGroup(plan2)

        groups = manager.planGroups()
        assert isinstance(groups, list)
        assert len(groups) == 2
        assert isinstance(groups[0], QgsLayerTreeGroup)
