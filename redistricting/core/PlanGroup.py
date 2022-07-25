# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - manage map layer group for redistricting plan

         begin                : 2022-05-31
         git sha              : $Format:%H$
         copyright            : (C) 2022 by Cryptodira
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
from __future__ import annotations
from typing import TYPE_CHECKING

from qgis.core import QgsProject, QgsLayerTreeGroup
from .Utils import tr

if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class PlanGroup:
    def __init__(self, plan: RedistrictingPlan):
        self._plan = plan
        self._group: QgsLayerTreeGroup = self.findGroup()
        if self._group:
            self._group.setName(self.groupName)

    @property
    def groupName(self):
        return tr('Redistricting Plan - {name}').format(
            name=self._plan.name,
        )

    def updateName(self):
        if self._group:
            self._group.setName(self.groupName)

    def updateLayers(self):
        if not self._group:
            self.createGroup()

        if self._plan.assignLayer and not self._group.findLayer(self._plan.assignLayer):
            self._group.addLayer(self._plan.assignLayer)
        if self._plan.distLayer and not self._group.findLayer(self._plan.distLayer):
            self._group.addLayer(self._plan.distLayer)

    def findGroup(self) -> QgsLayerTreeGroup:
        if self._plan.id:
            for g in QgsProject.instance().layerTreeRoot().children():
                if g.customProperty('redistricting-plan-id', None) == str(self._plan.id):
                    return g

        return None

    def removeGroup(self):
        if self._group:
            QgsProject.instance().layerTreeRoot().removeChildNode(self._group)

    def createGroup(self) -> QgsLayerTreeGroup:
        self._group = QgsLayerTreeGroup(self.groupName)
        self._group.setCustomProperty('redistricting-plan-id', str(self._plan.id))
        QgsProject.instance().layerTreeRoot().addChildNode(self._group)
