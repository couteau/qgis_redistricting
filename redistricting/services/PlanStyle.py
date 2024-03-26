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

from typing import (
    TYPE_CHECKING,
    List,
    Optional
)

from qgis.core import (
    Qgis,
    QgsCategorizedSymbolRenderer,
    QgsLimitedRandomColorRamp,
    QgsPalLayerSettings,
    QgsProject,
    QgsRendererCategory,
    QgsSimpleLineSymbolLayer,
    QgsSymbol,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsVectorLayerSimpleLabeling,
    QgsWkbTypes
)
from qgis.PyQt.QtCore import (
    QObject,
    Qt
)
from qgis.PyQt.QtGui import (
    QColor,
    QFont
)

from .PlanManager import PlanManager

if TYPE_CHECKING:
    from ..models import RedistrictingPlan

if Qgis.versionInt() > 33000:
    DISTRICT_GEOMETRY_TYPE = Qgis.GeometryType.Polygon
else:
    DISTRICT_GEOMETRY_TYPE = QgsWkbTypes.GeometryType.PolygonGeometry


class PlanStylerService(QObject):
    def __init__(self, planManager: PlanManager, parent: Optional[QObject]):
        super().__init__(parent)
        self._planManager = planManager
        self._planManager.planAdded.connect(self.copyStyles)
        QgsProject.instance().cleared.connect(self.clear)
        self._assignRenderer: QgsCategorizedSymbolRenderer = None
        self._distRenderer: QgsCategorizedSymbolRenderer = None
        self._labelsEnabled = False
        self._labeling: QgsVectorLayerSimpleLabeling = None
        self._numDistricts = 0
        self._attrName = "district"

    def clear(self):
        self._assignRenderer: QgsCategorizedSymbolRenderer = None
        self._distRenderer: QgsCategorizedSymbolRenderer = None
        self._labelsEnabled = False
        self._labeling = None
        self._numDistricts = 0
        self._attrName = "district"

    def stylePlan(self, plan: 'RedistrictingPlan'):
        if not self._assignRenderer:
            self.createRenderers(plan.numDistricts)
            self.createLabels()
        elif self._numDistricts < plan.numDistricts:
            self.createRenderers(plan.numDistricts)

        assignRenderer = self._assignRenderer.clone()
        distRenderer = self._distRenderer.clone()
        if plan.numDistricts < self._numDistricts:
            for c in range(plan.numDistricts, self._numDistricts+2):
                assignRenderer.deleteCategory(c)
                distRenderer.deleteCategory(c)

        plan.assignLayer.setRenderer(assignRenderer)
        plan.distLayer.setRenderer(distRenderer)
        plan.distLayer.setLabelsEnabled(True)
        plan.distLayer.setLabeling(self._labeling.clone())

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

        self._labeling = QgsVectorLayerSimpleLabeling(layerSettings)

    def createRenderers(self, numDistricts):
        symbol = QgsSymbol.defaultSymbol(DISTRICT_GEOMETRY_TYPE)
        symbol.symbolLayer(0).setStrokeStyle(Qt.PenStyle(Qt.NoPen))
        symbol.symbolLayer(0).setStrokeWidth(0)
        symbol.symbolLayer(0).setFillColor(QColor('#c8cfc9'))

        categoryList: List[QgsRendererCategory] = []
        for dist in range(0, numDistricts+1):
            category = QgsRendererCategory()
            category.setValue(None if dist == 0 else dist)
            category.setSymbol(symbol.clone())
            category.setLabel(str(dist))
            categoryList.append(category)

        ramp = QgsLimitedRandomColorRamp(count=self._numDistricts+1, satMin=50, satMax=100)

        assignRenderer = QgsCategorizedSymbolRenderer(self._attrName, categoryList)
        assignRenderer.updateColorRamp(ramp)
        idx = assignRenderer.categoryIndexForValue(None)
        assignRenderer.updateCategorySymbol(idx, symbol)
        self._assignRenderer = assignRenderer

        symbol = QgsSymbol.defaultSymbol(DISTRICT_GEOMETRY_TYPE)
        symbol.symbolLayer(0).setStrokeColor(QColor('white'))
        symbol.symbolLayer(0).setStrokeStyle(Qt.PenStyle(Qt.SolidLine))
        symbol.symbolLayer(0).setStrokeWidth(2)
        symbol.symbolLayer(0).setFillColor(QColor('#c8cfc9'))
        symbol.appendSymbolLayer(QgsSimpleLineSymbolLayer(QColor('#384450'), 1.0, Qt.SolidLine))

        categoryList: List[QgsRendererCategory] = []
        for dist in range(0, self._numDistricts+1):
            d = assignRenderer.categories()[dist]  # pylint: disable=unsubscriptable-object
            color = QColor(d.symbol().color())
            sym = symbol.clone()
            sym.symbolLayer(0).setFillColor(color)
            category = QgsRendererCategory()
            category.setValue(None if dist == 0 else dist)
            category.setSymbol(sym)
            category.setLabel(str(dist))
            categoryList.append(category)
        categoryList[0].setRenderState(False)

        self._distRenderer = QgsCategorizedSymbolRenderer(self._attrName, categoryList)

    def copyStyles(self, plan: RedistrictingPlan):
        if self._numDistricts > plan.numDistricts:
            return

        self._numDistricts = plan.numDistricts
        self._attrName = plan.distField
        self._assignRenderer = plan.assignLayer.renderer().clone()
        self._distRenderer = plan.distLayer.renderer().clone()

        if self._labeling is None:
            if plan.distLayer.labelsEnabled():
                self._labeling = plan.distLayer.labeling().clone()
            else:
                self.createLabels()
