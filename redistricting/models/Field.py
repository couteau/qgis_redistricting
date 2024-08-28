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
from typing import Union

from qgis.core import (
    QgsApplication,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsField,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    QMetaType,
    QVariant,
    pyqtSignal
)
from qgis.PyQt.QtGui import QIcon

from .base import (
    Factory,
    RdsBaseModel,
    rds_property
)


class RdsField(RdsBaseModel):
    captionChanged = pyqtSignal()

    layer: QgsVectorLayer = rds_property(private=True)
    field: str = rds_property(private=True)
    caption: str = None

    def __pre_init__(self):
        self._icon: QIcon = None
        self._expression: QgsExpression = None
        self._context: QgsExpressionContext = None
        self._prepared = False
        self._errors = []

    def __key__(self):
        return self._field

    @rds_property(private=True, notify=captionChanged)
    def caption(self) -> str:
        if self._caption is None:
            if self.qgsField() is not None:
                self._caption = self.qgsField().displayName() or self.field
            else:
                self._caption = self.field

        return self._caption

    @caption.setter
    def caption(self, value: str):
        self._caption = value

    @property
    def fieldName(self):
        if self.field.isidentifier():
            return self.field

        if self._caption and self._caption.isidentifier():
            return self._caption.lower()

        return re.sub(r'[^\w]+', '_', (self._caption or self._field).lower())

    @property
    def expression(self):
        if self._expression is None:
            self._expression = QgsExpression(self.field)

            if self._expression.hasParserError():
                self._errors = [e.errorMsg for e in self._expression.parserErrors()]  # pylint: disable=not-an-iterable

        return self._expression

    @property
    def icon(self):
        if self._icon is None:
            if self.expression.isField():
                self._icon = self.layer.fields().iconForField(self.fieldIndex(), False)
            else:
                self._icon = QgsApplication.getThemeIcon("/mIconExpression.svg")

        return self._icon

    def _createContext(self) -> QgsExpressionContext:
        return QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(self.layer))

    def errors(self) -> list[str]:
        return self._errors

    def isValid(self) -> bool:
        if self._expression is None or self._context is None:
            self.validate()
        return not self._errors

    def isExpression(self) -> bool:
        return not self.expression.isField()

    def validate(self) -> bool:
        self._errors = []
        if not self.expression.isValid():
            return False

        if self._context is None:
            self._context = self._createContext()

        if not self._prepared:
            self._prepared = self.expression.prepare(self._context)
            if not self._prepared:
                self._errors.append(self.expression.evalErrorString())
                return False

        return True

    def prepare(self, context: QgsExpressionContext = None) -> bool:
        self._prepared = False
        if context is None:
            self._context = self._createContext()
        else:
            self._context = context
        return self.validate()

    def getValue(self, feature: QgsFeature = None):
        if feature is not None:
            if not self._prepared:
                self.prepare()
            self._context.setFeature(feature)
        return self._expression.evaluate(self._context)

    def fieldIndex(self):
        return QgsExpression.expressionToLayerFieldIndex(self.field, self.layer)

    def fieldType(self) -> QMetaType.Type:
        index = self.fieldIndex()
        if index != -1:
            return self.layer.fields().field(index).type()

        if self._prepared or self.prepare():
            f = self._context.feature()
            if f is None or not f.isValid():
                f = next(self.layer.getFeatures(), None)

            if f is not None:
                v = self.getValue(f)
                # TODO: change this type .typeId() when QGIS moves to Qt 6
                return QVariant(v).type()

        return QMetaType.UnknownType

    def qgsField(self) -> QgsField:
        idx = self.fieldIndex()
        if idx == -1:
            return None

        return self.layer.fields().field(idx)

    def makeQgsField(self, name: str = None) -> QgsField:
        if name is None:
            name = self.fieldName

        t = self.fieldType()

        if t is QMetaType.UnknownType:
            return None

        return QgsField(name, t)


class RdsGeoField(RdsField):
    def _createNameField(self):
        l = self.getRelatedLayer()
        if l is None:
            return None

        if l.fields().lookupField("name") != -1:
            nameField = RdsField(l, "name")
        elif self.layer.fields().lookupField(l, "name30") != -1:
            nameField = RdsField(l, "name30")
        elif self.layer.fields().lookupField("name20") != -1:
            nameField = RdsField(l, "name20")
        elif self.layer.fields().lookupField("name10") != -1:
            nameField = RdsField(l, "name10")
        else:
            nameField = None

        return nameField

    nameField: RdsField = rds_property(private=True, factory=Factory(_createNameField))

    def getRelation(self):
        index = QgsExpression.expressionToLayerFieldIndex(self._field, self._layer)
        if index != -1:
            relations = self.layer.referencingRelations(index)
            if relations:
                return relations[0]

        return None

    def getRelatedLayer(self):
        rel = self.getRelation()
        if rel:
            return rel.referencedLayer()

        return None

    def getName(self, feature) -> str:
        rel = self.getRelation()
        f = rel.getReferencedFeature(feature)
        if f is not None:
            return self._nameField.getValue(f)

        return None


class RdsDataField(RdsField):
    sumFieldChanged = pyqtSignal()
    pctBaseChanged = pyqtSignal()

    sumField: bool = rds_property(
        private=True,
        fvalid=lambda inst, value: value and inst.isNumeric(),
        notify=sumFieldChanged,
        factory=Factory(lambda self: self.isNumeric())
    )
    pctBase: Union[str, None] = rds_property(
        private=True,
        fvalid=lambda inst, value: None if not inst.isNumeric() else value,
        notify=pctBaseChanged,
        default=None
    )

    def isNumeric(self):
        return self.fieldType() in (QVariant.Double, QVariant.Int, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong)
