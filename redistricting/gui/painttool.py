# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - Map tool for painting districts

        begin                : 2022-01-05
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
from enum import IntEnum
from typing import (
    Iterable,
    List
)

from qgis.core import (
    Qgis,
    QgsFeature,
    QgsGeometry
)
from qgis.gui import (
    QgsMapCanvas,
    QgsMapMouseEvent,
    QgsMapToolIdentify,
    QgsRubberBand
)
from qgis.PyQt.QtCore import (
    QRect,
    Qt,
    pyqtSignal
)
from qgis.PyQt.QtGui import (
    QColor,
    QCursor,
    QKeyEvent,
    QPixmap
)

from ..models import RdsPlan


class PaintMode(IntEnum):
    PaintByGeography = 1
    PaintRectangle = 2
    SelectByGeography = 3


class PaintDistrictsTool(QgsMapToolIdentify):
    paintingStarted = pyqtSignal(int, int)
    paintFeatures = pyqtSignal("PyQt_PyObject", int, object, bool)  # features, target, source (int|none), endEdit
    paintingComplete = pyqtSignal()
    paintingCanceled = pyqtSignal()
    selectFeatures = pyqtSignal("PyQt_PyObject", int, int, "PyQt_PyObject")

    MinPixelZoom = 20

    def __init__(self, canvas: QgsMapCanvas):
        super().__init__(canvas)
        self._distTarget: int = None
        self._distSource: int = None

        pixmap = QPixmap(':/plugins/redistricting/paintcursor.svg')
        self.setCursor(QCursor(
            pixmap, 3, 18)
        )

        self._paintMode: PaintMode = PaintMode.PaintByGeography
        self._selectRect = QRect(0, 0, 0, 0)
        self._dragging = False
        self._rubberBand = None
        self._plan = None
        self._layer = None

        self.buttonsPressed = Qt.MouseButton.NoButton

    @property
    def plan(self):
        return self._plan

    @plan.setter
    def plan(self, value: RdsPlan):
        if self._plan != value:
            self._plan = value
            self._layer = self._plan.assignLayer if self._plan is not None else None
            self._distTarget = None
            self._distSource = None

    def targetDistrict(self, buttons=Qt.MouseButton.LeftButton):
        if buttons & Qt.MouseButton.RightButton != Qt.MouseButton.NoButton:
            return self._distSource

        return self._distTarget

    def sourceDistrict(self, buttons=Qt.MouseButton.LeftButton):
        if buttons & Qt.MouseButton.RightButton != Qt.MouseButton.NoButton:
            return self._distTarget

        return self._distSource

    def setSourceDistrict(self, value):
        self._distSource = value

    def setTargetDistrict(self, value):
        self._distTarget = value

    @property
    def paintMode(self) -> PaintMode:
        return self._paintMode

    @paintMode.setter
    def paintMode(self, value: PaintMode):
        self._paintMode = value

    def _paintFeatures(self, features: Iterable[QgsFeature], target, source, endEdit=True):
        self.paintFeatures.emit(features, target, source, endEdit)

    def _selectFeatures(
        self,
        features: Iterable[QgsFeature],
        target,
        source,
        behavior: Qgis.SelectBehavior = Qgis.SelectBehavior.SetSelection,
    ):
        self.selectFeatures.emit(features, target, source, behavior)

    def canvasPressEvent(self, e: QgsMapMouseEvent):
        self.buttonsPressed = e.buttons()
        if self._layer is None or self.targetDistrict(self.buttonsPressed) is None:
            return

        if self.buttonsPressed & (Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton) == Qt.MouseButton.NoButton:
            return

        if self._paintMode == PaintMode.PaintByGeography:
            r = self.searchRadiusMU(self.canvas())
            self.setCanvasPropertiesOverrides(r/4)
            self.paintingStarted.emit(
                self.targetDistrict(self.buttonsPressed),
                self.sourceDistrict(self.buttonsPressed)
            )
        elif self._paintMode in {PaintMode.PaintRectangle, PaintMode.SelectByGeography}:
            self._selectRect.setRect(e.pos().x(), e.pos().y(), e.pos().x()+1, e.pos().y()+1)

    def canvasReleaseEvent(self, e: QgsMapMouseEvent):
        if self._layer is None:
            return

        if e.buttons() & self.buttonsPressed != Qt.MouseButton.NoButton:
            return

        if self.buttonsPressed & (Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton) == Qt.MouseButton.NoButton:
            return

        if self.targetDistrict(self.buttonsPressed) is None:
            return

        self.restoreCanvasPropertiesOverrides()

        if self._paintMode == PaintMode.PaintByGeography:
            results: list[QgsMapToolIdentify.IdentifyResult] = \
                self.identify(e.pos().x(), e.pos().y(), [self._layer])
            if not results:
                if self._dragging:
                    self._dragging = False
                    self.paintingComplete.emit()
                else:
                    self.paintingCanceled.emit()
                return

            self._paintFeatures(
                (r.mFeature for r in results),
                self.targetDistrict(self.buttonsPressed),
                self.sourceDistrict(self.buttonsPressed)
            )
            self._dragging = False
            self.paintingComplete.emit()
        elif self._paintMode in {PaintMode.PaintRectangle, PaintMode.SelectByGeography}:
            if self._dragging:
                self._dragging = False
                tooShort = (self._selectRect.topLeft() - self._selectRect.bottomRight()) \
                    .manhattanLength() < self.MinPixelZoom
                if not tooShort:
                    geom = self._rubberBand.asGeometry()
                self._rubberBand.hide()
                self._rubberBand = None
            else:
                tooShort = False
                geom = QgsGeometry.fromPointXY(self.toMapCoordinates(e.pos()))

            if not tooShort:
                results: List[QgsMapToolIdentify.IdentifyResult] = \
                    self.identify(geom, QgsMapToolIdentify.DefaultQgsSetting,
                                  [self._layer], QgsMapToolIdentify.VectorLayer)
                if self._paintMode == PaintMode.SelectByGeography:
                    self._selectFeatures(
                        (r.mFeature for r in results),
                        self.targetDistrict(self.buttonsPressed),
                        self.sourceDistrict(self.buttonsPressed)
                    )
                else:
                    self._paintFeatures(
                        (r.mFeature for r in results),
                        self.targetDistrict(self.buttonsPressed),
                        self.sourceDistrict(self.buttonsPressed)
                    )

        self.buttonsPressed = Qt.MouseButton.NoButton

    def canvasMoveEvent(self, e: QgsMapMouseEvent):
        buttons = e.buttons()
        if self._layer is None or self.targetDistrict(buttons) is None:
            return

        if buttons & (Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton) == Qt.MouseButton.NoButton:
            return

        if self._paintMode == PaintMode.PaintByGeography:
            results: List[QgsMapToolIdentify.IdentifyResult] = \
                self.identify(e.pos().x(), e.pos().y(), [self._layer])

            if not results:
                return

            self._dragging = True
            self._paintFeatures(
                (r.mFeature for r in results),
                self.targetDistrict(buttons),
                self.sourceDistrict(buttons),
                False
            )
        elif self._paintMode in {PaintMode.PaintRectangle, PaintMode.SelectByGeography}:
            if not self._dragging:
                self._dragging = True
                self._rubberBand = QgsRubberBand(self.canvas(), Qgis.GeometryType.Polygon)
                color = QColor(Qt.GlobalColor.blue) \
                    if self._paintMode == PaintMode.PaintRectangle \
                    else QColor(Qt.GlobalColor.lightGray)
                color.setAlpha(63)
                self._rubberBand.setColor(color)
                self._selectRect.setTopLeft(e.pos())
            self._selectRect.setBottomRight(e.pos())
            if self._rubberBand:
                self._rubberBand.setToCanvasRectangle(self._selectRect)
                self._rubberBand.show()

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key.Key_Escape:
            self.canvas().unsetMapTool(self)
