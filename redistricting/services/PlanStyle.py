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
    Optional
)

from qgis.core import (
    Qgis,
    QgsCategorizedSymbolRenderer,
    QgsFillSymbol,
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
    from ..models import RdsPlan

if Qgis.versionInt() > 33000:
    DISTRICT_GEOMETRY_TYPE = Qgis.GeometryType.Polygon
else:
    DISTRICT_GEOMETRY_TYPE = QgsWkbTypes.GeometryType.PolygonGeometry


class PlanStylerService(QObject):
    def __init__(self, planManager: PlanManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._planManager = planManager
        self._planManager.planAdded.connect(self.copyStyles)
        QgsProject.instance().cleared.connect(self.clear)
        self._ramp: QgsLimitedRandomColorRamp = None
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

    def stylePlan(self, plan: 'RdsPlan'):
        if not self._assignRenderer:
            self.createRenderers(plan.numDistricts)
            self.createLabels()
        elif self._numDistricts < plan.numDistricts:
            self.createRenderers(plan.numDistricts)

        if self._labeling is None:
            self.createLabels()

        assignRenderer = self._assignRenderer.clone()
        distRenderer = self._distRenderer.clone()
        if plan.numDistricts < self._numDistricts:
            for c in range(plan.numDistricts, self._numDistricts+2):
                assignRenderer.deleteCategory(c)
                distRenderer.deleteCategory(c)
        assignRenderer.setClassAttribute(plan.distField)
        distRenderer.setClassAttribute(plan.distField)

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
        if self._ramp:
            self._ramp.setCount(numDistricts+1)
        else:
            self._ramp = QgsLimitedRandomColorRamp(count=numDistricts+1, satMin=50, satMax=100)

        self.createAssignmentRenderer(numDistricts)
        self.createDistrictRenderer(numDistricts)
        self._numDistricts = numDistricts

    def createAssignmentRenderer(self, numDistricts: int):
        symbol: QgsFillSymbol = QgsSymbol.defaultSymbol(DISTRICT_GEOMETRY_TYPE)
        symbol.symbolLayer(0).setStrokeStyle(Qt.PenStyle(Qt.NoPen))
        symbol.symbolLayer(0).setStrokeWidth(0)

        assignRenderer = QgsCategorizedSymbolRenderer(self._attrName)

        for dist in range(0, numDistricts+1):
            sym = symbol.clone()
            sym.setColor(QColor('#c8cfc9') if dist == 0 else self._ramp.color(dist))
            category = QgsRendererCategory(
                None if dist == 0 else dist,
                sym,
                str(dist) if dist != 0 else 'Unassigned'
            )
            assignRenderer.addCategory(category)

        self._assignRenderer = assignRenderer

    def createDistrictRenderer(self, numDistricts: int):
        symbol = QgsSymbol.defaultSymbol(DISTRICT_GEOMETRY_TYPE)
        symbol.symbolLayer(0).setStrokeColor(QColor('white'))
        symbol.symbolLayer(0).setStrokeStyle(Qt.PenStyle(Qt.SolidLine))
        symbol.symbolLayer(0).setStrokeWidth(2)
        symbol.appendSymbolLayer(QgsSimpleLineSymbolLayer(QColor('#384450'), 1.0, Qt.SolidLine))

        distRenderer = QgsCategorizedSymbolRenderer(self._attrName)
        for dist in range(0, numDistricts+1):
            sym = symbol.clone()
            sym.symbolLayer(0).setFillColor(QColor('#c8cfc9') if dist == 0 else self._ramp.color(dist))
            category = QgsRendererCategory(
                None if dist == 0 else dist,
                sym,
                str(dist) if dist != 0 else 'Unassigned',
                dist != 0
            )
            distRenderer.addCategory(category)

        self._distRenderer = distRenderer

    def copyStyles(self, plan: RdsPlan):
        if self._numDistricts >= plan.numDistricts:
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
