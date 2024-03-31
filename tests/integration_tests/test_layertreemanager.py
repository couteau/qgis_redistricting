from uuid import uuid4

from pytest_mock import MockerFixture
from qgis.core import QgsProject
from qgis.gui import QgisInterface

from redistricting.models import RedistrictingPlan


class TestLayerTreeManager:
    def test_remove_plan(self, manager, qgis_new_project, layertree_plan):
        project = QgsProject.instance()
        manager.createGroup(layertree_plan)
        assert project.layerTreeRoot().findGroup(layertree_plan.name) is not None
        manager.removeGroup(layertree_plan)
        assert project.layerTreeRoot().findGroup(layertree_plan.name) is None

    def test_bring_plan_to_top(self, manager, qgis_new_project, mocker: MockerFixture, qgis_iface: QgisInterface, block_layer, assign_layer, dist_layer):
        project = QgsProject.instance()
        project.addMapLayer(block_layer, True)

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
