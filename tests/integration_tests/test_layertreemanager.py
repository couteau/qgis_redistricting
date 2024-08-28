import pytest
from qgis.core import QgsProject

from redistricting.models import (
    RdsPlan,
    deserialize_model
)
from redistricting.services import LayerTreeManager
from redistricting.services.DistrictIO import DistrictReader

# pylint: disable=unused-argument,protected-access


class TestLayerTreeManager:
    @pytest.fixture
    def manager(self):
        manager = LayerTreeManager()
        return manager

    @pytest.fixture
    def plan2(self, block_layer, assign_layer, dist_layer):
        p: RdsPlan = deserialize_model(RdsPlan, {
            'name': 'test2',
            'deviation': 0.025,
            'geo-layer': block_layer.id(),
            'geo-id-field': 'geoid',
            'dist-field': 'district',
            'pop-field': 'pop_total',
            'pop-fields': [
                {'layer': block_layer.id(),
                 'field': 'vap_total',
                 'caption': 'VAP'}
            ],
            'assign-layer': assign_layer.id(),
            'dist-layer': dist_layer.id(),
            'num-districts': 5,
            'data-fields': [
                {'layer': block_layer.id(),
                 'field': 'vap_ap_black',
                 'caption': 'APBVAP',
                 'sum-field': True,
                 'pct-base': 'vap_total'},
                {'layer': block_layer.id(),
                 'field': 'vap_nh_white',
                 'caption': 'WVAP',
                 'sum-field': True,
                 'pct-base': 'vap_total'},
                {'layer': block_layer.id(),
                 'field': 'vap_hispanic',
                 'caption': 'HVAP',
                 'sum-field': True,
                 'pct-base': 'vap_total'},
            ],
            'geo-fields': [
                {'layer': assign_layer.id(),
                 'field': 'vtdid',
                 'caption': 'VTD'}
            ],
            'stats': {
                'total-population': 227036,
            }

        }, None)

        r = DistrictReader(dist_layer, popField='pop_total')
        for d in r.readFromLayer():
            if d.district == 0:
                p.districts[0].update(d)
            else:
                p.districts.append(d)

        yield p

        p.deleteLater()

    def test_remove_plan(self, manager: LayerTreeManager, qgis_new_project, plan: RdsPlan):
        project = QgsProject.instance()
        manager.createGroup(plan)
        assert project.layerTreeRoot().findGroup(plan.name) is not None
        manager.removeGroup(plan)
        assert project.layerTreeRoot().findGroup(plan.name) is None

    def test_bring_plan_to_top(self, manager: LayerTreeManager, qgis_new_project, plan, plan2, qgis_iface, block_layer):
        project = QgsProject.instance()
        manager.createGroup(plan)
        manager.createGroup(plan2)

        qgis_iface.setActiveLayer(block_layer)
        manager.bringPlanToTop(plan2)
        assert project.layerTreeRoot().hasCustomLayerOrder()
