# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - save/load plans to/from the project file 

        begin                : 2022-01-15
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
from uuid import UUID
from typing import Any, List, Sized
from packaging import version
from enum import Enum
import json
from qgis.PyQt.QtXml import QDomDocument, QDomElement
from qgis.core import QgsProject, QgsReadWriteContext
from .utils import tr
from .Plan import RedistrictingPlan

schemaVersion = version.parse('1.0.0')


class ProjectStorage:
    def __init__(self, project: QgsProject, doc: QDomDocument, context: QgsReadWriteContext = None):
        self._project = project
        self._doc = doc
        self._context = context
        self._pnode = None
        self._version = schemaVersion
        self._getPluginNode()

    def migrate(self):
        """Migrate plugin node in project file to new schema

            currently does nothing - here for the future in case 
            the json schema/storage format changes
        """
        # perform migration
        self._version = schemaVersion

    def _getPluginNode(self):
        docNode = self._doc.documentElement()
        props = docNode.namedItem('properties')
        if props.isNull():
            return None
        node = props.namedItem('redistricting')
        if node.isElement():
            self._pnode = node.toElement()
            self._version = version.parse(self._pnode.attribute('version', '0.0.0'))
            if self._version < schemaVersion:
                self.migrate()

        return None

    def _createPluginNode(self):
        docNode = self._doc.documentElement()
        props = docNode.namedItem('properties')
        if props.isNull():
            props = self._doc.createElement('properties')
            docNode.appendChild(props)
        node = props.namedItem('redistricting')
        if node.isElement():
            self._pnode = node.toElement()
            self._version = version.parse(self._pnode.attribute('version', '0.0.0'))
            if self._version < schemaVersion:
                self.migrate()
        else:
            props.removeChild(node)
            node = self._doc.createElement('redistricting')
            node.setAttribute('version', str(schemaVersion))
            props.appendChild(node)
            self._pnode = node
            self._version = schemaVersion
            return node

    def _findPlanByUUID(self, uuid: UUID):
        if self._pnode is None:
            return None
        nodes = self._pnode.elementsByTagName('redistricting-plan')
        for i in range(0, nodes.length()):
            node = nodes.item(i).toElement()
            if node.hasAttribute('id') and node.attribute('id') == str(uuid):
                return node
        return None

    def readPlan(self, planNode: QDomElement):
        if not planNode.hasAttributes():
            if self._context:
                self._context.pushMessage(tr('Invalid redistricting plan found: plan has no attributes'))
        else:
            c = planNode.firstChild()
            if c and c.isCDATASection():
                planJson = json.loads(c.toCDATASection().data())
                return RedistrictingPlan.deserialize(planJson, parent=self._project)

        planNode.parentNode().removeChild(planNode)
        return None

    def serializeToNode(self, data: dict[str, Any], nodeName):
        node = self._doc.createElement(nodeName)
        for key, value in data.items():
            if isinstance(value, Sized) and len(value) == 0:
                continue

            if isinstance(value, dict):
                node.appendChild(self.serializeToNode(value, key))
            elif isinstance(value, (list, set)):
                if key[-1] == 's':
                    childKey = key[:-1]
                else:
                    childKey = key
                groupNode = self._doc.createElement(key)
                for item in value:
                    childNode = self.serializeToNode(item, childKey)
                    groupNode.appendChild(childNode)

                node.appendChild(groupNode)
            elif isinstance(value, Enum):
                node.setAttribute(key, int(value))
            else:
                node.setAttribute(key, str(value))

        return node

    def writePlan(self, plan: RedistrictingPlan):
        pnode = self._createPluginNode()
        data = plan.serialize()
        jplan = json.dumps(data)
        node = self._doc.createElement('redistricting-plan')
        node.setAttribute('name', plan.name)
        node.setAttribute('uuid', str(plan.id))
        node.appendChild(self._doc.createCDATASection(jplan))

        oldNode = self._findPlanByUUID(plan.id)
        if oldNode is not None:
            pnode.replaceChild(node, oldNode)
        else:
            pnode.appendChild(node)

    def readRedistrictingPlans(self) -> List[RedistrictingPlan]:
        if self._pnode is None:
            return []

        plans = []
        nodes = self._pnode.elementsByTagName('redistricting-plan')
        for n in range(nodes.length()):
            node = nodes.item(n).toElement()
            plan = self.readPlan(node)
            if plan is not None:
                plans.append(plan)
        return plans

    def readActivePlan(self):
        if self._pnode is None:
            return False
        anode = self._pnode.namedItem('active-plan')
        if anode.isElement():
            try:
                uuid = UUID(anode.toElement().text())
                return uuid
            except ValueError:
                # ignore malformed uuids
                pass

        return False

    def writeActivePlan(self, plan: RedistrictingPlan):
        pnode = self._createPluginNode()
        if pnode is not None:
            anode = self._doc.createElement('active-plan')
            anode.appendChild(self._doc.createTextNode(str(plan.id)))
            pnode.appendChild(anode)
