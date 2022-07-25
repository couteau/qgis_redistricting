# -*- coding: utf-8 -*-
"""
/***************************************************************************
 * *
 *   This program is free software; you can redistribute it and / or modify *
 *   it under the terms of the GNU General Public License as published by *
 *   the Free Software Foundation; either version 2 of the License, or *
 *   (at your option) any later version. *
 * *
 ***************************************************************************/
"""

from enum import Enum
from typing import Any, Dict, List, Sized
from uuid import UUID
from qgis.core import QgsProject, QgsReadWriteContext, QgsMessageLog
from qgis.PyQt.QtCore import QTextStream, QByteArray
from qgis.PyQt.QtXml import QDomDocument, QDomElement, QDomNode
from PyQt5.QtXmlPatterns import QXmlSchema, QXmlSchemaValidator
from .Plan import RedistrictingPlan
from .Utils import tr

planSchema = b"""<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
    <xs:element name="redistricting">
        <xs:complexType>
            <xs:sequence>
                <xs:element name="redistricting-plan" minOccurs="0" maxOccurs="unbounded">
                    <xs:complexType>
                        <xs:all>
                            <xs:element name="districts" minOccurs="0">
                                <xs:complexType>
                                    <xs:sequence>
                                        <xs:element name="district" minOccurs="0" maxOccurs="unbounded">
                                            <xs:complexType>
                                                <xs:attribute name="district" type="xs:integer" use="required" />
                                                <xs:attribute name="members" type="xs:integer" default="1" />
                                                <xs:attribute name="name" type="xs:string" />
                                                <xs:attribute name="description" type="xs:string" />
                                            </xs:complexType>
                                        </xs:element>
                                    </xs:sequence>
                                </xs:complexType>
                            </xs:element>
                            <xs:element name="data-fields" minOccurs="0">
                                <xs:complexType>
                                    <xs:sequence>
                                        <xs:element name="data-field" minOccurs="0" maxOccurs="unbounded">
                                            <xs:complexType>
                                                <xs:attribute name="layer" type="xs:string" use="required" />
                                                <xs:attribute name="field" type="xs:string" use="required" />
                                                <xs:attribute name="expression" type="xs:boolean" use="required" />
                                                <xs:attribute name="caption" type="xs:string" />
                                                <xs:attribute name="sum" type="xs:boolean" default="true" />
                                                <xs:attribute name="pctbase" type="xs:integer" default="0" />
                                            </xs:complexType>
                                        </xs:element>
                                    </xs:sequence>
                                </xs:complexType>
                            </xs:element>
                            <xs:element name="geo-fields" minOccurs="0">
                                <xs:complexType>
                                    <xs:sequence>
                                        <xs:element name="geo-field" minOccurs="0" maxOccurs="unbounded">
                                            <xs:complexType>
                                                <xs:attribute name="layer" type="xs:string" use="required" />
                                                <xs:attribute name="field" type="xs:string" use="required" />
                                                <xs:attribute name="expression" type="xs:boolean" use="required" />
                                                <xs:attribute name="caption" type="xs:string" />
                                            </xs:complexType>
                                        </xs:element>
                                    </xs:sequence>
                                </xs:complexType>
                            </xs:element>
                        </xs:all>
                        <xs:attribute name="id" type="xs:string" use="required" />
                        <xs:attribute name="name" type="xs:string" use="required" />
                        <xs:attribute name="description" type="xs:string" />
                        <xs:attribute name="total-population" type="xs:integer" default="0" />
                        <xs:attribute name="num-districts" type="xs:integer" use="required" />
                        <xs:attribute name="num-seats" type="xs:integer" />
                        <xs:attribute name="deviation" type="xs:decimal" default="0" />
                        <xs:attribute name="cut-edges" type="xs:integer" default="0" />
                        <xs:attribute name="pop-layer" type="xs:string" use="required" />
                        <xs:attribute name="dist-layer" type="xs:string" use="required" />
                        <xs:attribute name="assign-layer" type="xs:string" use="required" />
                        <xs:attribute name="src-layer" type="xs:string" />
                        <xs:attribute name="geo-id-field" type="xs:string" use="required" />
                        <xs:attribute name="geo-id-display" type="xs:string" />
                        <xs:attribute name="dist-field" type="xs:string" use="required" />
                        <xs:attribute name="pop-field" type="xs:string" use="required" />
                        <xs:attribute name="vap-field" type="xs:string" />
                        <xs:attribute name="cvap-field" type="xs:string" />
                        <xs:attribute name="src-id-field" type="xs:string" />
                    </xs:complexType>
                </xs:element>
                <xs:element name="active-plan" minOccurs="0" maxOccurs="1" type="xs:string"></xs:element>
            </xs:sequence>
        </xs:complexType>
    </xs:element>
</xs:schema>"""


PlanSchema = {
    'id': str,
    'name': str,
    'description': str,
    'total-population': int,
    'num-districts': int,
    'num-seats': int,
    'deviation': float,
    'cut-edges': int,
    'pop-layer': str,
    'assign-layer': str,
    'dist-layer': str,
    'geo-id-field': str,
    'geo-id-display': str,
    'dist-field': str,
    'pop-field': str,
    'vap-field': str,
    'cvap-field': str,
    'src-layer': str,
    'src-id-field': str,
    'data-fields': {
        'layer': str,
        'field': str,
        'caption': str,
        'expression': bool,
        'sum': bool,
        'pctbase': int,
    },
    'geo-fields': {
        'layer': str,
        'field': str,
        'caption': str,
        'expression': bool,
    },
    'districts': {
        'district': int,
        'members': int,
        'name': str,
        'description': str
    },
}


class ProjectStorage:
    _doc: QDomDocument
    _context: QgsReadWriteContext = None
    _project: QgsProject = None
    _pnode: QDomElement

    def __init__(self, project: QgsProject, doc: QDomDocument, context: QgsReadWriteContext = None):
        self._project = project
        self._doc = doc
        self._context = context
        self._pnode = self._getPluginNode()

    def _getPluginNode(self):
        docNode = self._doc.documentElement()
        props = docNode.namedItem('properties')
        if props.isNull():
            return None
        node = props.namedItem('redistricting')
        if node.isElement():
            a = QByteArray()
            stream = QTextStream(a)
            node.save(stream, 2)
            schema = QXmlSchema()
            schema.load(planSchema)
            if schema.isValid():
                validator = QXmlSchemaValidator(schema)
                valid = validator.validate(a)
                if not valid:
                    QgsMessageLog.logMessage(tr('Plugin node doesn\'t validate'))

            return node.toElement()

        return None

    def _createPluginNode(self):
        docNode = self._doc.documentElement()
        props = docNode.namedItem('properties')
        if props.isNull():
            props = self._doc.createElement('properties')
            docNode.appendChild(props)
        node = props.namedItem('redistricting')
        if node.isElement():
            return node.toElement()
        else:
            props.removeChild(node)
            node = self._doc.createElement('redistricting')
            props.appendChild(node)
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

    def _readPlanAttribute(self, planNode: QDomElement, attribute, required=True, default=None):
        if not planNode.hasAttribute(attribute):
            if required and self._context:
                self._context.pushMessage(
                    tr(f'Invalid redistricting plan found: missing {attribute} attribute')
                )
            return default
        return planNode.attribute(attribute)

    def _readField(self, fieldNode: QDomElement) -> Dict[str, Any]:
        return {
            'layer': self._readPlanAttribute(fieldNode, 'layer'),
            'field': self._readPlanAttribute(fieldNode, 'field'),
            'caption': self._readPlanAttribute(fieldNode, 'caption'),
            'expression': bool(int(self._readPlanAttribute(
                fieldNode, 'expression')))
        }

    def _readDataField(self, fieldNode: QDomElement) -> Dict[str, Any]:
        return self._readField(fieldNode) | {
            'sum': bool(int(self._readPlanAttribute(fieldNode, 'sum'))),
            'pctpop': bool(int(self._readPlanAttribute(fieldNode, 'pctpop'))),
            'pctvap': bool(int(self._readPlanAttribute(fieldNode, 'pctvap'))),
            'pctcvap': bool(int(self._readPlanAttribute(fieldNode, 'pctcvap')))
        }

    def _readDistrict(self, distNode: QDomElement) -> Dict[str, Any]:
        return {
            'district': int(self._readPlanAttribute(distNode, 'district')),
            'name': self._readPlanAttribute(distNode, 'name'),
            'members': int(self._readPlanAttribute(distNode, 'members')),
            'description': self._readPlanAttribute(distNode, 'description')
        }

    def readItem(self, node: QDomNode, schema=None) -> dict:
        if schema is None:
            schema = PlanSchema
        d = {}
        attributes = node.attributes()
        for i in range(0, len(attributes)):
            attr = attributes.item(i).toAttr()
            name = attr.name()
            value = attr.value()
            if name in schema and schema[name] is bool:
                d[name] = value.lower() not in ('0', 'no', 'false')
            elif name in schema:
                try:
                    d[name] = schema[name](value)
                except ValueError:
                    ...
            else:
                d[name] = value
        children = node.childNodes()
        for i in range(0, len(children)):
            collection = children.item(i)
            if collection.hasChildNodes():
                name = collection.nodeName()
                d[name] = []
                items = collection.childNodes()
                for j in range(0, len(items)):
                    d[name].append(self.readItem(items.item(j), schema[name] if name in schema else None))
        return d

    def readPlan(self, planNode: QDomElement):
        if not planNode.hasAttributes():
            if self._context:
                self._context.pushMessage(tr('Invalid redistricting plan found: plan has no attributes'))
            planNode.parentNode().removeChild(planNode)
            return None

        return RedistrictingPlan.deserialize(self.readItem(planNode), parent=self._project)

    def serializeToNode(self, data: dict[str, Any], nodeName):
        node = self._doc.createElement(nodeName)
        for key, value in data.items():
            if isinstance(value, Sized) and len(value) == 0:
                continue

            if isinstance(value, dict):
                node.appendChild(self.serializeToNode(item, childKey))
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
            else:
                if isinstance(value, Enum):
                    node.setAttribute(key, int(value))
                else:
                    node.setAttribute(key, value)

        return node

    def writePlan(self, plan: RedistrictingPlan):
        pnode = self._createPluginNode()
        data = plan.serialize()
        node = self.serializeToNode(data, 'redistricting-plan')

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
