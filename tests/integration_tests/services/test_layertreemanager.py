"""QGIS Redistricting Plugin - integration tests

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
from qgis.core import QgsProject

from redistricting.models import (
    RdsPlan,
    deserialize
)
from redistricting.services import LayerTreeManager
from redistricting.services.districtio import DistrictReader

# pylint: disable=unused-argument,protected-access


class TestLayerTreeManager:
    @pytest.fixture
    def manager(self):
        manager = LayerTreeManager(QgsProject.instance())
        return manager

    @pytest.fixture
    def plan2(self, block_layer, assign_layer, dist_layer):
        p: RdsPlan = deserialize(RdsPlan, {
            "name": "test2",
            "deviation": 0.025,
            "geo-layer": block_layer.id(),
            "geo-id-field": "geoid",
            "dist-field": "district",
            "pop-field": "pop_total",
            "pop-fields": [
                {"layer": block_layer.id(),
                 "field": "vap_total",
                 "caption": "VAP"}
            ],
            "assign-layer": assign_layer.id(),
            "dist-layer": dist_layer.id(),
            "num-districts": 5,
            "data-fields": [
                {"layer": block_layer.id(),
                 "field": "vap_ap_black",
                 "caption": "APBVAP",
                 "sum-field": True,
                 "pct-base": "vap_total"},
                {"layer": block_layer.id(),
                 "field": "vap_nh_white",
                 "caption": "WVAP",
                 "sum-field": True,
                 "pct-base": "vap_total"},
                {"layer": block_layer.id(),
                 "field": "vap_hispanic",
                 "caption": "HVAP",
                 "sum-field": True,
                 "pct-base": "vap_total"},
            ],
            "geo-fields": [
                {"layer": assign_layer.id(),
                 "field": "vtdid",
                 "caption": "VTD"}
            ],
            "metrics": {
                "total-population": {"vale": 227036},
            }

        })

        r = DistrictReader(dist_layer, popField="pop_total")
        for d in r.readFromLayer():
            if d.district == 0:
                p.districts[0].update(d)
            else:
                p.districts.append(d)

        yield p

        p.deleteLater()

    def test_remove_plan(self, manager: LayerTreeManager, plan: RdsPlan):
        project = QgsProject.instance()
        manager.createGroup(plan)
        assert project.layerTreeRoot().findGroup(plan.name) is not None
        manager.removeGroup(plan)
        assert project.layerTreeRoot().findGroup(plan.name) is None

    def test_bring_plan_to_top(self, manager: LayerTreeManager, plan, plan2, qgis_iface, block_layer):
        project = QgsProject.instance()
        manager.createGroup(plan)
        manager.createGroup(plan2)

        qgis_iface.setActiveLayer(block_layer)
        manager.bringPlanToTop(plan2)
        assert project.layerTreeRoot().hasCustomLayerOrder()
