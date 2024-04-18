"""QGIS Redistricting Plugin - manage interaction between LayerTree and plans

        begin                : 2024-03-20
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Cryptodira
        email                : stuart@cryptodira.org

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
from typing import (
    TYPE_CHECKING,
    Optional
)
from uuid import (
    UUID,
    uuid4
)

from qgis.core import (
    QgsLayerTreeGroup,
    QgsProject
)
from qgis.PyQt.QtCore import QObject

from ..utils import tr

if TYPE_CHECKING:
    from ..models import RedistrictingPlan


class LayerTreeManager(QObject):
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.root = QgsProject.instance().layerTreeRoot()

    @property
    def planRoot(self):
        for group in self.root.findGroups(False):
            if group.customProperty('redistricting-plan-root', False) is True:
                break
            if group.customProperty('redistricting-plan-id', None) is not None:
                return self.root
        else:
            name = tr("Redistricting Plans")
            if self.root.findGroup(name) is not None:
                name = f"{name}-{str(uuid4())}"
            group = self.root.addGroup(name)
            group.setCustomProperty('redistricting-plan-root', True)

        return group

    def createGroup(self, plan: "RedistrictingPlan"):
        if not plan.isValid():
            raise ValueError(tr("Cannot add incomplete plan to layer tree"))

        group = QgsLayerTreeGroup(plan.name)
        group.setCustomProperty('redistricting-plan-id', str(plan.id))
        group.addLayer(plan.assignLayer)
        group.addLayer(plan.distLayer)
        self.planRoot.addChildNode(group)
        return group

    def removeGroup(self, plan: "RedistrictingPlan"):
        group = self.getGroupForPlan(plan)
        if group is not None:
            self.planRoot.removeChildNode(group)

    def planGroups(self) -> list[QgsLayerTreeGroup]:
        return [g for g in self.planRoot.findGroups(False) if g.customProperty('redistricting-plan-id', None) is not None]

    def getGroupForPlan(self, plan: "RedistrictingPlan"):
        if plan.id:
            for g in self.planRoot.findGroups():
                if g.customProperty('redistricting-plan-id', None) == str(plan.id):
                    return g

        return None

    def planIdFromGroup(self, group: QgsLayerTreeGroup):
        planid = group.customProperty('redistricting-plan-id', None)
        if planid is None:
            return None

        return UUID(planid)

    def bringPlanToTop(self, plan: "RedistrictingPlan"):
        group = self.getGroupForPlan(plan)
        if group is None:
            return

        groups = self.planGroups()
        groups.remove(group)
        groups.insert(0, group)

        plan_layers = [l.layer() for g in groups for l in g.findLayers()]

        self.root.setHasCustomLayerOrder(False)
        order = self.root.layerOrder()
        new_order = []
        plans_added = False

        for layer in order:
            if layer in plan_layers:
                if not plans_added:
                    new_order.extend(plan_layers)
                    plans_added = True
                continue

            new_order.append(layer)

        self.root.setHasCustomLayerOrder(True)
        self.root.setCustomLayerOrder(new_order)

    def renameGroupAndLayers(self, plan: "RedistrictingPlan"):
        group = self.getGroupForPlan(plan)
        if group is not None:
            group.setName(plan.name)
            plan.assignLayer.setName(f'{plan.name}_assignments')
            plan.distLayer.setName(f'{plan.name}_districts')
