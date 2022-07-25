# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QGIS Redistricting Plugin - Map tool for painting districts
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
 ***************************************************************************/

/***************************************************************************
 * *
 *   This program is free software; you can redistribute it and / or modify *
 *   it under the terms of the GNU General Public License as published by *
 *   the Free Software Foundation; either version 2 of the License, or *
 *   (at your option) any later version. *
 * *
 ***************************************************************************/
"""
from enum import IntEnum
from typing import Iterable, List

from qgis.gui import QgsMapCanvas, QgsMapMouseEvent, QgsMapToolIdentify, QgsRubberBand
from qgis.core import QgsFeature, QgsWkbTypes, QgsGeometry, QgsVectorLayer
from qgis.PyQt.QtCore import Qt, QRect
from qgis.PyQt.QtGui import QKeyEvent, QCursor, QPixmap, QColor
from ..core import RedistrictingPlan, PlanEditor, tr


class PaintMode(IntEnum):
    PaintByGeography = 1
    PaintRectangle = 2
    SelectByGeography = 3


class PaintDistrictsTool(QgsMapToolIdentify):
    PAINT_CURSOR = [
        # columns rows colors chars-per-pixel
        "16 16 3 1 ",
        "  c None",
        ". c black",
        "X c white",
        # pixels
        "         X.X    ",
        "         X..X   ",
        "        X....X  ",
        "        X.....X ",
        "       X.......X",
        "       X.....XX ",
        "       X.....X  ",
        "     XXXX...X   ",
        "    X...XXXX    ",
        "    X....X      ",
        "   X.....X      ",
        "   X.....X      ",
        "  X.....X       ",
        " XX....X        ",
        "X....XX         ",
        ".XXXX           "
    ]

    PAINT_CURSOR24 = [
        # columns rows colors chars-per-pixel
        "24 24 3 1 ",
        "  c None",
        ". c black",
        "+ c white",
        # pixels
        "                 ++     ",
        "                +..++   ",
        "                +....+  ",
        "               +......+ ",
        "               +.......+",
        "              +........+",
        "             +........+ ",
        "             +.......+  ",
        "            +.......+   ",
        "           +.......+    ",
        "           +......+     ",
        "         +++++...+      ",
        "       ++....++..+      ",
        "      +.......+++       ",
        "     +........+         ",
        "     +.........+        ",
        "    +..........+        ",
        "    +..........+        ",
        "    +..........+        ",
        "   +..........+         ",
        "   +..........+         ",
        "  +.........++          ",
        "  +.......++            ",
        " +.+++++++              "
    ]
    PAINT_CURSOR32 = [
        # columns rows colors chars-per-pixel
        "32 32 20 1 ",
        "  c None",
        ". c black",
        "X c #010101",
        "o c #020202",
        "O c gray1",
        "+ c #040404",
        "@ c gray2",
        "# c #060606",
        "$ c #070707",
        "% c gray3",
        "& c #090909",
        "* c #0B0B0B",
        "= c #0C0C0C",
        "- c gray5",
        "; c gray6",
        ": c #101010",
        "> c #111111",
        ", c gray7",
        "< c #131313",
        "1 c #151515",
        # pixels
        "                        -       ",
        "                       @@@      ",
        "                       @@@@     ",
        "                      @@@@@@-   ",
        "                     @@@@@@@@@  ",
        "                     @@@@@@@@@@ ",
        "                    @@@@@@@@@@@-",
        "                   -@@@@@@@@@@- ",
        "                   @@@@@@@@@@@  ",
        "                  @@@@@@@@@@@   ",
        "                 -@@@@@@@@@@    ",
        "                 @@@@@@@@@@     ",
        "                @@@@@@@@@@      ",
        "                @@@@@@@@@       ",
        "                @@@@@@@@>       ",
        "                 >@@@@@-        ",
        "           -@@@    @@@@         ",
        "          @@@@@@>   @@          ",
        "         @@@@@@@@@              ",
        "        @@@@@@@@@@@             ",
        "       @@@@@@@@@@@@@            ",
        "       @@@@@@@@@@@@@            ",
        "      -@@@@@@@@@@@@@            ",
        "      @@@@@@@@@@@@@@            ",
        "      @@@@@@@@@@@@@@            ",
        "      @@@@@@@@@@@@@>            ",
        "     @@@@@@@@@@@@@@             ",
        "     @@@@@@@@@@@@@-             ",
        "    @@@@@@@@@@@@@@              ",
        "    @@@@@@@@@@@@-               ",
        "   @@@@@@@@@@@>                 ",
        " @@@@@@@@-                      "
    ]

    MinPixelZoom = 20

    def __init__(self, canvas: QgsMapCanvas, plan: RedistrictingPlan = None):
        super().__init__(canvas)
        self._plan = None
        self._geoField = None
        self._distTarget = None
        self._distSource = None

        pixmap = QPixmap(PaintDistrictsTool.PAINT_CURSOR24)
        self.setCursor(QCursor(
            pixmap, 2, 23)
        )

        self._paintMode = PaintMode.PaintByGeography
        self._selectRect = QRect(0, 0, 0, 0)
        self._dragging = False
        self._rubberBand = None

        self.plan = plan

    @ property
    def plan(self):
        return self._plan

    @ plan.setter
    def plan(self, value: RedistrictingPlan):
        if self._plan != value:
            self._plan = value
            self._layer = self._plan.assignLayer if self._plan is not None else None

            self._assignmentEditor = None
            if self._plan and self._plan.geoFields and self._geoField not in self._plan.geoFields:
                self._geoField = None
            self._distTarget = None
            self._distSource = None

    @ property
    def targetDistrict(self):
        return self._distTarget

    @ property
    def sourceDistrict(self):
        return self._distSource

    @ property
    def geoField(self):
        return self._geoField

    @property
    def paintMode(self):
        return self._paintMode

    @paintMode.setter
    def paintMode(self, value):
        self._paintMode = value

    def _paintFeatures(self, features: Iterable[QgsFeature]):
        if self._geoField is not None and self._geoField != self._plan.geoIdField:
            values = {str(feature.attribute(self._geoField)) for feature in features}
            features = self._assignmentEditor.getDistFeatures(
                self._geoField, values, self._distTarget, self._distSource)

        self._assignmentEditor.assignFeaturesToDistrict(
            features, self._distTarget, self._distSource)
        self._layer.triggerRepaint()

    def _selectFeatures(
        self,
        features: Iterable[QgsFeature],
        behavior: QgsVectorLayer.SelectBehavior = QgsVectorLayer.SetSelection
    ):
        if self.geoField is not None and self._geoField != self._plan.geoIdField:
            values = {str(feature.attribute(self._geoField)) for feature in features}
            features = self._assignmentEditor.getDistFeatures(
                self._geoField, values, self._distTarget, self._distSource)

        self._layer.selectByIds([f.id() for f in features], behavior)

    def canvasPressEvent(self, e: QgsMapMouseEvent):
        if self._layer is None or \
                self._distTarget is None:
            return

        if e.buttons() & Qt.LeftButton == Qt.NoButton:
            return

        if self._paintMode == PaintMode.PaintByGeography:
            r = self.searchRadiusMU(self.canvas())
            self.setCanvasPropertiesOverrides(r/4)
            self._layer.beginEditCommand(tr('Assign features to district {}').format(
                str(self.targetDistrict)))
        elif self._paintMode in {PaintMode.PaintRectangle, PaintMode.SelectByGeography}:
            self._selectRect.setRect(e.x(), e.y(), e.x()+1, e.y()+1)

    def canvasReleaseEvent(self, e: QgsMapMouseEvent):
        if self._layer is None or \
                self._distTarget is None:
            return

        if e.button() != Qt.LeftButton:
            return

        self.restoreCanvasPropertiesOverrides()

        if self._paintMode == PaintMode.PaintByGeography:
            results: List[QgsMapToolIdentify.IdentifyResult] = \
                self.identify(e.x(), e.y(), [self._layer])
            if not results:
                self._layer.destroyEditCommand()
                return
            self._paintFeatures(r.mFeature for r in results)
            self._layer.endEditCommand()
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
                    self._selectFeatures(r.mFeature for r in results)
                else:
                    self._paintFeatures(r.mFeature for r in results)

    def canvasMoveEvent(self, e: QgsMapMouseEvent):
        if self._layer is None or \
                self._distTarget is None:
            return

        if e.buttons() & Qt.LeftButton == Qt.NoButton:
            return

        if self._paintMode == PaintMode.PaintByGeography:
            results: List[QgsMapToolIdentify.IdentifyResult] = \
                self.identify(e.x(), e.y(), [self._layer])

            self._paintFeatures(r.mFeature for r in results)
        elif self._paintMode in {PaintMode.PaintRectangle, PaintMode.SelectByGeography}:
            if not self._dragging:
                self._dragging = True
                self._rubberBand = QgsRubberBand(self.canvas(), QgsWkbTypes.PolygonGeometry)
                color = QColor(Qt.blue) \
                    if self._paintMode == PaintMode.PaintRectangle \
                    else QColor(Qt.lightGray)
                color.setAlpha(63)
                self._rubberBand.setColor(color)
                self._selectRect.setTopLeft(e.pos())
            self._selectRect.setBottomRight(e.pos())
            if self._rubberBand:
                self._rubberBand.setToCanvasRectangle(self._selectRect)
                self._rubberBand.show()

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key_Escape:
            self.canvas().unsetMapTool(self)

    def canActivate(self):
        return self._layer is not None and \
            self._distTarget is not None

    def activate(self):
        self._assignmentEditor = PlanEditor(self.plan, self)
        return super().activate()

    def deactivate(self):
        self._assignmentEditor = None
        return super().deactivate()

    def setGeoField(self, value):
        if value is not None and self._plan is not None and \
                value != self._plan.geoIdField and \
                self._plan.geoFields and value not in self._plan.geoFields:
            raise ValueError(tr('Attempt to set invalid geography field on paint tool'))
        self._geoField = value

    def setSourceDistrict(self, value):
        self._distSource = value

    def setTargetDistrict(self, value):
        self._distTarget = value
