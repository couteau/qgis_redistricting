
# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RedistrictingPlan
        QGIS Redistricting plugin core logic
                              -------------------
        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from enum import IntEnum
from typing import Any, Dict, Optional
from qgis.PyQt.QtCore import QObject, pyqtSignal, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsVectorLayer,
    QgsFeature,
    QgsField)
from .Utils import makeFieldName, tr
from .Exception import RdsException


class Field(QObject):

    fieldChanged = pyqtSignal('PyQt_PyObject')

    def __init__(self, layer: QgsVectorLayer, field: str, isExpression: bool = None,
                 caption: str = None, parent: Optional['QObject'] = None):
        super().__init__(parent)
        if layer is None or field is None:
            raise ValueError()

        self._layer = None
        self._error = None
        self._field = field
        self._isExpression = isExpression if isExpression is not None else not field.isidentifier()
        self._caption = caption or field
        self._index = -1
        self.setLayer(layer)

    def setLayer(self, layer: QgsVectorLayer):
        if self._isExpression:
            if not self._validateExpr(layer):
                raise RdsException(tr('Expression "{}" invalid for layer {}').format(self.field, layer.name()))
            self._icon = QgsApplication.getThemeIcon("/mIconExpression.svg")
        else:
            self._index = layer.fields().lookupField(self._field)
            if self._index == -1:
                raise RdsException(tr('Field {} not found in layer {}').format(self._field, layer.name()))

            self._icon = layer.fields().iconForField(self._index, False)
            if self._caption is None or self._caption == self._field:
                self._caption = layer.fields().field(self._index).displayName() or self._caption

        self._layer = layer

    def __copy__(self):
        cls = self.__class__
        result = cls.__new__(cls)
        super(Field, result).__init__(self.parent())
        result.__dict__.update(self.__dict__)
        return result

    def __deepcopy__(self, memo):
        return self.__copy__()

    def serialize(self):
        return {
            'layer': self._layer.id(),
            'field': self._field,
            'expression': self._isExpression,
            'caption': self._caption
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any], parent: Optional['QObject'] = None):
        if not 'field' in data:
            return None
        layer = QgsProject.instance().mapLayer(data.get('layer'))
        return cls(layer, data['field'], data.get('expression', False), data.get('caption'), parent=parent)

    def _validateExpr(self, layer):
        if not self._isExpression:
            return True

        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
        e = QgsExpression(self._field)
        return e.prepare(context)

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
    def icon(self) -> QIcon:
        return self._icon

    @property
    def caption(self) -> str:
        return self._caption

    @caption.setter
    def caption(self, value):
        self._caption = value
        self.fieldChanged.emit(self)

    def hasError(self):
        return self._error is not None

    def error(self):
        return self._error

    def makeQgsField(self, context: QgsExpressionContext = None, name: str = None):
        if name is None:
            name = self.fieldName

        if self.isExpression:
            if not context:
                context = QgsExpressionContext()
                context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.layer))
                context.setFeature(next(self.layer.getFeatures()))
            expr = QgsExpression(self.field)
            result = expr.evaluate(context)
            if expr.hasEvalError():
                self._error = expr.evalErrorString()
                field = None
            else:
                t = QVariant(result).type()
                field = QgsField(name, QVariant.LongLong if t == QVariant.Int else t)
        else:
            i = self.layer.fields().lookupField(self.field)
            if i == -1:
                self._error = tr(f'Field {self.field} not found')
                field = None
            else:
                field = QgsField(name, self.layer.fields().field(i).type())

        return field

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

        return result


class BasePopulation(IntEnum):
    NOPCT = 0
    TOTALPOP = 1
    VAP = 2
    CVAP = 3


class DataField(Field):
    def __init__(self, layer: QgsVectorLayer, field: str, isExpression: bool = None,
                 caption=None, sumfield=None, pctbase=None, parent: Optional['QObject'] = None):
        super().__init__(layer, field, isExpression, caption, parent)

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

        f = field.lower()
        cvap = not isExpression and (f[:4] == 'cvap' or f[-4:] == 'cvap')
        vap = not isExpression and not cvap and (
            f[:3] == 'vap' or f[-3:] == 'vap' or f[:4] == 'p003' or f[:4] == 'p004')

        if not self.isNumeric or isExpression:
            pctbase = BasePopulation.NOPCT
        elif pctbase is None:
            pctbase = BasePopulation.CVAP if cvap \
                else BasePopulation.VAP if vap \
                else BasePopulation.TOTALPOP

        self._pctbase = pctbase

    @property
    def sum(self) -> bool:
        return self._sum

    @sum.setter
    def sum(self, value: bool):
        if self._sum != value:
            self._sum = value
            self.fieldChanged.emit(self)

    @property
    def pctbase(self) -> BasePopulation:
        return self._pctbase

    @pctbase.setter
    def pctbase(self, value: BasePopulation):
        if self._pctbase != value:
            self._pctbase = value
            self.fieldChanged.emit(self)

    @property
    def pctpop(self) -> bool:
        return self._pctbase == BasePopulation.TOTALPOP

    @pctpop.setter
    def pctpop(self, value: bool):
        self.pctbase = BasePopulation.TOTALPOP if value else BasePopulation.NOPCT

    @property
    def pctvap(self) -> bool:
        return self._pctbase == BasePopulation.VAP

    @pctvap.setter
    def pctvap(self, value: bool):
        self.pctbase = BasePopulation.VAP if value else BasePopulation.NOPCT

    @property
    def pctcvap(self) -> bool:
        return self._pctbase == BasePopulation.CVAP

    @pctcvap.setter
    def pctcvap(self, value: bool):
        self.pctbase = BasePopulation.CVAP if value else BasePopulation.NOPCT

    def serialize(self):
        return super().serialize() | {
            'sum': self.sum,
            'pctbase': self.pctbase,
        }

    @classmethod
    def deserialize(cls, data, parent: Optional['QObject'] = None):
        if field := super().deserialize(data, parent):
            field.sum = data.get('sum', field.sum)
            field.pctbase = BasePopulation(data.get('pctbase', field.pctbase))

        return field
