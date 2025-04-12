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
    QgsColorRamp,
    QgsFillSymbol,
    QgsPalLayerSettings,
    QgsPresetSchemeColorRamp,
    QgsProject,
    QgsRendererCategory,
    QgsSimpleLineSymbolLayer,
    QgsSymbol,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsVectorLayer,
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

from ..models import colors
from .planmgr import PlanManager

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
        self._ramp: QgsColorRamp = None
        self._assignRenderer: QgsCategorizedSymbolRenderer = None
        self._distRenderer: QgsCategorizedSymbolRenderer = None
        self._labelsEnabled = False
        self._labeling: QgsVectorLayerSimpleLabeling = None
        self._numDistricts = 0

    def clear(self):
        self._assignRenderer: QgsCategorizedSymbolRenderer = None
        self._distRenderer: QgsCategorizedSymbolRenderer = None
        self._labelsEnabled = False
        self._labeling = None
        self._numDistricts = 0

    def checkRenderers(self, numDistricts):
        if not self._assignRenderer:
            self.createRenderers(numDistricts)
            self.createLabels()
        elif self._numDistricts < numDistricts:
            self.createRenderers(numDistricts)

        if self._labeling is None:
            self.createLabels()

    def styleAssignLayer(self, layer: QgsVectorLayer, numDistricts: int, distField: str):
        self.checkRenderers(numDistricts)
        assignRenderer = self._assignRenderer.clone()
        if numDistricts < self._numDistricts:
            for c in range(numDistricts, self._numDistricts+2):
                assignRenderer.deleteCategory(c)
        assignRenderer.setClassAttribute(distField)
        layer.setRenderer(assignRenderer)

    def styleDistLayer(self, layer: QgsVectorLayer, numDistricts: int, distField: str):
        self.checkRenderers(numDistricts)
        distRenderer = self._distRenderer.clone()
        if numDistricts < self._numDistricts:
            for c in range(numDistricts, self._numDistricts+2):
                distRenderer.deleteCategory(c)
        distRenderer.setClassAttribute(distField)
        layer.setRenderer(distRenderer)
        layer.setLabelsEnabled(True)
        layer.setLabeling(self._labeling.clone())

    def stylePlan(self, plan: 'RdsPlan'):
        self.styleAssignLayer(plan.assignLayer, plan.numDistricts, plan.distField)
        self.styleDistLayer(plan.distLayer, plan.numDistricts, plan.distField)

    def createRamp(self, numDistricts) -> QgsColorRamp:
        ramp = QgsPresetSchemeColorRamp(colors.colors[:numDistricts+1])
        return ramp

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
        self._numDistricts = max(self._numDistricts, numDistricts)
        if not self._ramp or self._numDistricts >= self._ramp.count():
            self._ramp = self.createRamp(numDistricts)

        self.createAssignmentRenderer(numDistricts)
        self.createDistrictRenderer(numDistricts)

    def createAssignmentRenderer(self, numDistricts: int):
        symbol: QgsFillSymbol = QgsSymbol.defaultSymbol(DISTRICT_GEOMETRY_TYPE)
        symbol.symbolLayer(0).setStrokeStyle(Qt.PenStyle.NoPen)
        symbol.symbolLayer(0).setStrokeWidth(0)

        assignRenderer = QgsCategorizedSymbolRenderer("district")

        for dist in range(0, numDistricts+1):
            sym = symbol.clone()
            sym.setColor(self._ramp.color(dist/self._numDistricts))
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
        symbol.symbolLayer(0).setStrokeStyle(Qt.PenStyle.SolidLine)
        symbol.symbolLayer(0).setStrokeWidth(2)
        symbol.appendSymbolLayer(QgsSimpleLineSymbolLayer(QColor('#384450'), 1.0, Qt.PenStyle.SolidLine))

        distRenderer = QgsCategorizedSymbolRenderer("district")
        for dist in range(0, numDistricts+1):
            sym = symbol.clone()
            sym.symbolLayer(0).setFillColor(self._ramp.color(dist/self._numDistricts))
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
        self._assignRenderer = plan.assignLayer.renderer().clone()
        self._distRenderer = plan.distLayer.renderer().clone()

        if self._labeling is None:
            if plan.distLayer.labelsEnabled():
                self._labeling = plan.distLayer.labeling().clone()
            else:
                self.createLabels()
