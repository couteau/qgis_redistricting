# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - plan style manager

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
from typing import TYPE_CHECKING, List

from qgis.PyQt.QtCore import Qt, QObject
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    QgsSymbol,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsRandomColorRamp,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling,
    QgsSimpleLineSymbolLayer,
)
if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class PlanStyler(QObject):
    def __init__(self, plan: RedistrictingPlan):
        super().__init__(plan)
        self._plan = plan
        self._assignLayer = plan.assignLayer
        self._distLayer = plan.distLayer
        self._distField = plan.distField
        self._numDistricts = plan.numDistricts

    @classmethod
    def style(cls, plan, sourcePlan):
        styler = cls(plan)
        if sourcePlan:
            styler.copyStyles(sourcePlan)
        else:
            styler.createRenderer()
            styler.createLabels()

    def createRenderer(self):
        symbol = QgsSymbol.defaultSymbol(self._distLayer.geometryType())
        symbol.symbolLayer(0).setStrokeStyle(Qt.PenStyle(Qt.NoPen))
        symbol.symbolLayer(0).setStrokeWidth(0)
        symbol.symbolLayer(0).setFillColor(QColor('#c8cfc9'))

        categoryList: List[QgsRendererCategory] = []
        for dist in range(0, self._numDistricts+1):
            category = QgsRendererCategory(
                None if dist == 0 else dist,
                symbol.clone(),
                str(dist)
            )
            categoryList.append(category)

        ramp = QgsRandomColorRamp()
        ramp.setTotalColorCount(self._numDistricts+1)

        renderer = QgsCategorizedSymbolRenderer(self._distField, categoryList)
        renderer.updateColorRamp(ramp)
        idx = renderer.categoryIndexForValue(None)
        renderer.updateCategorySymbol(idx, symbol)
        self._assignLayer.setRenderer(renderer)

        symbol = QgsSymbol.defaultSymbol(self._distLayer.geometryType())
        symbol.symbolLayer(0).setStrokeColor(QColor('white'))
        symbol.symbolLayer(0).setStrokeStyle(Qt.PenStyle(Qt.SolidLine))
        symbol.symbolLayer(0).setStrokeWidth(2)
        symbol.symbolLayer(0).setFillColor(QColor('#c8cfc9'))
        symbol.appendSymbolLayer(QgsSimpleLineSymbolLayer(
            QColor('#384450'), 1.0, Qt.SolidLine))

        categoryList: List[QgsRendererCategory] = []
        for dist in range(0, self._numDistricts+1):
            d = renderer.categories()[dist]
            color = QColor(d.symbol().color())
            sym = symbol.clone()
            sym.symbolLayer(0).setFillColor(color)
            category = QgsRendererCategory(
                None if dist == 0 else dist,
                sym,
                str(dist)
            )
            categoryList.append(category)
        categoryList[0].setRenderState(False)

        renderer = QgsCategorizedSymbolRenderer(self._distField, categoryList)
        self._distLayer.setRenderer(renderer)

    def createLabels(self):
        bufferSettings = QgsTextBufferSettings()
        bufferSettings.setEnabled(True)
        bufferSettings.setSize(1)
        bufferSettings.setColor(QColor("white"))

        textFormat = QgsTextFormat()
        textFormat.setFont(QFont("Arial Black", 20))
        textFormat.setSize(20)
        textFormat.setBuffer(bufferSettings)

        layerSettings = QgsPalLayerSettings()
        layerSettings.setFormat(textFormat)
        layerSettings.fieldName = "name"
        layerSettings.placement = QgsPalLayerSettings.Horizontal

        layerSettings = QgsVectorLayerSimpleLabeling(layerSettings)
        self._distLayer.setLabelsEnabled(True)
        self._distLayer.setLabeling(layerSettings)

    def copyStyles(self, fromPlan: 'RedistrictingPlan'):
        self._assignLayer.setRenderer(fromPlan.assignLayer.renderer().clone())
        self._distLayer.setRenderer(fromPlan.distLayer.renderer().clone())
        if fromPlan.distLayer.labelsEnabled():
            self._distLayer.setLabelsEnabled(True)
            self._distLayer.setLabeling(fromPlan.distLayer.labeling().clone())
