# -*- coding: utf-8 -*-
"""Geographic and Demographic Field classes

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
import re
from copy import copy
from typing import (
    Any,
    Dict,
    Optional,
    Union
)

from qgis.core import (
    QgsApplication,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsField,
    QgsProject,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QIcon

from ..utils import tr


def makeFieldName(field: "Field"):
    if field.isExpression:
        name = (field.caption or field.field).lower()
        if not name.isidentifier():
            name = re.sub(r'[^\w]+', '_', name)
    else:
        name = field.field

    return name


class Field:
    def __init__(
        self,
        layer: QgsVectorLayer,
        field: str,
        isExpression: Union[bool, None] = None,  # None = autodetect
        caption: Optional[str] = None
    ):
        if layer is None or field is None:
            raise ValueError()

        self._layer: QgsVectorLayer = None
        self._error = None
        self._field = field
        self._isExpression = isExpression if isExpression is not None else not field.isidentifier()
        self._caption = caption or field
        self._index = -1
        self.setLayer(layer)

    def setLayer(self, layer: QgsVectorLayer):
        if not self.validate(layer):
            raise ValueError(self._error)

        if self._isExpression:
            self._icon = QgsApplication.getThemeIcon("/mIconExpression.svg")
        else:
            self._icon = layer.fields().iconForField(self._index, False)
            if self._caption is None or self._caption == self._field:
                self._caption = layer.fields().field(self._index).displayName() or self._caption

        self._layer = layer

    def serialize(self) -> dict[str, Any]:
        return {
            'layer': self._layer.id(),
            'field': self._field,
            'expression': self._isExpression,
            'caption': self._caption
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]):
        if not 'field' in data:
            return None
        layer = QgsProject.instance().mapLayer(data.get('layer'))
        return cls(layer, data['field'], data.get('expression', False), data.get('caption'))

    def _validateExpr(self, layer):
        if not self._isExpression:
            return True

        self._error = None
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
        e = QgsExpression(self._field)
        result = e.prepare(context)
        if e.hasEvalError():
            self._error = e.evalErrorString()
        elif e.hasParserError():
            self._error = e.parserErrorString()
        return result

    def validate(self, layer: QgsVectorLayer = None):
        if layer is None:
            layer = self._layer

        self._error = None
        if self._isExpression:
            if not self._validateExpr(layer):
                self._error = tr('Expression "{}" invalid for layer {}: {}').format(
                    self.field, layer.name(), self._error)
                return False

        else:
            self._index = layer.fields().lookupField(self._field)
            if self._index == -1:
                self._error = tr('Field {} not found in layer {}').format(self._field, layer.name())
                return False

        return True

    @property
    def layer(self) -> QgsVectorLayer:
        return self._layer

    @property
    def field(self) -> str:
        return self._field

    @property
    def isExpression(self) -> bool:
        return self._isExpression

    @property
    def fieldName(self):
        return makeFieldName(self)

    @property
    def index(self):
        return self._index

    @property
    def icon(self) -> QIcon:
        return self._icon

    @property
    def caption(self) -> str:
        return self._caption

    @caption.setter
    def caption(self, value):
        self._caption = value

    def hasError(self):
        return self._error is not None

    def error(self):
        return self._error

    def fieldType(self, context: QgsExpressionContext = None, layer: QgsVectorLayer = None):
        if layer is None:
            layer = self._layer

        if self.isExpression:
            if not context:
                context = QgsExpressionContext()
                context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
                context.setFeature(next(layer.getFeatures()))
            expr = QgsExpression(self.field)
            result = expr.evaluate(context)
            if expr.hasEvalError():
                self._error = expr.evalErrorString()
                return None

            t = QVariant(result).type()
        else:
            i = layer.fields().lookupField(self.field)
            if i == -1:
                self._error = tr(f'Field {self.field} not found')
                return None

            t = layer.fields().field(i).type()

        return t

    def makeQgsField(self, context: QgsExpressionContext = None, name: str = None, layer=None):
        self._error = None

        if name is None:
            name = self.fieldName

        t = self.fieldType(context, layer)
        if t is None:
            return None

        return QgsField(name, QVariant.LongLong if t == QVariant.Int else t)

    def getValue(self, feature: QgsFeature, context: QgsExpressionContext = None):
        if self._isExpression:
            self._error = None
            e = QgsExpression(self.field)
            if not context:
                context = QgsExpressionContext()
                context.appendScopes(
                    QgsExpressionContextUtils.globalProjectLayerScopes(self._layer))
            context.setFeature(feature)
            result = e.evaluate(context)
            if e.hasEvalError():
                self._error = e.evalErrorString()
                return None
        else:
            result = feature[self.field]

        if isinstance(result, QVariant):
            result = None

        return result


class GeoField(Field):
    def __init__(
        self,
        layer: QgsVectorLayer,
        field: str,
        isExpression: Union[bool, None] = None,
        caption: Optional[str] = None
    ):
        self._nameField: Field = None
        super().__init__(layer, field, isExpression, caption)

    def getRelatedLayer(self):
        if self._layer and self._index != -1:
            relations = self._layer.referencingRelations(self._index)
            if relations:
                return relations[0].referencedLayer()
        return None

    def setLayer(self, layer: QgsVectorLayer):
        super().setLayer(layer)
        if self._nameField is None:
            l = self.getRelatedLayer()
            if l:
                if l.fields().lookupField("name") != -1:
                    self.setNameField("name")
                elif self._layer.fields().lookupField("name20") != -1:
                    self.setNameField("name20")
                elif self._layer.fields().lookupField("name10") != -1:
                    self.setNameField("name10")

    @property
    def nameField(self):
        return self._nameField

    def setNameField(self, value: Union[Field, str]):
        if isinstance(value, str):
            self._nameField = Field(self.getRelatedLayer(), value)
        else:
            self._nameField = copy(value)

    def serialize(self):
        nf = {'name-field': self._nameField.serialize()} \
            if self._nameField else {}
        return super().serialize() | nf

    @classmethod
    def deserialize(cls, data: dict[str, Any]):
        field = super().deserialize(data)
        if field:
            nf = data.get('name-field')
            if nf:
                field._nameField = Field.deserialize(nf)  # pylint: disable=protected-access

        return field


class DataField(Field):
    def __init__(
        self,
        layer: QgsVectorLayer,
        field: str,
        isExpression: Union[bool, None] = None,
        caption: Optional[str] = None,
        sumfield: Optional[bool] = None,
        pctbase: Optional[Union[Field, str]] = None
    ):
        super().__init__(layer, field, isExpression, caption)

        if self._isExpression:
            e = QgsExpression(field)
            context = QgsExpressionContext()
            context.appendScopes(
                QgsExpressionContextUtils.globalProjectLayerScopes(layer))
            feature = next(layer.getFeatures())
            context.setFeature(feature)
            result = e.evaluate(context)
            if e.hasEvalError():
                self._error = e.evalErrorString()
                self.isNumeric = False
            else:
                self.isNumeric = isinstance(result, (int, float))
        elif self._index != -1:
            self.isNumeric = layer.fields().field(self._index).isNumeric()

        # sum
        self._sum = self.isNumeric if sumfield is None else (sumfield and self.isNumeric)

        if not self.isNumeric or isExpression:
            self._pctbase = None
        else:
            if isinstance(pctbase, Field):
                self._pctbase = pctbase.fieldName
            else:
                self._pctbase = pctbase

    @property
    def sum(self) -> bool:
        return self._sum

    @sum.setter
    def sum(self, value: bool):
        if value and not self.isNumeric:
            return

        if self._sum != value:
            self._sum = value

    @property
    def pctbase(self) -> str:
        return self._pctbase

    @pctbase.setter
    def pctbase(self, value: Union[str, Field]):
        if not self.isNumeric and value is not None:
            return

        if isinstance(value, Field):
            value = value.fieldName

        if self._pctbase != value:
            self._pctbase = value

    def serialize(self):
        return super().serialize() | {
            'sum': self.sum,
            'pctbase': self.pctbase,
        }

    @classmethod
    def deserialize(cls, data):
        instance = super().deserialize(data)
        if instance:
            instance.sum = data.get('sum', instance.sum) if instance.isNumeric else False  # pylint: disable=no-member
            instance.pctbase = data.get('pctbase')

        return instance
