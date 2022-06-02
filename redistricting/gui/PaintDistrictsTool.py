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
from typing import Optional
from PyQt5.QtGui import QCursor, QPixmap
from PyQt5.QtWidgets import QApplication

from qgis.gui import QgsMapToolIdentifyFeature, QgsMapCanvas
from qgis.core import QgsVectorLayer


class PaintDistrictsTool(QgsMapToolIdentifyFeature):
    def __init__(self, canvas: QgsMapCanvas, vl: Optional[QgsVectorLayer] = ...):
        super().__init__(canvas, vl)

        self._cursor = QCursor(
            QPixmap(':/plugins/redistricting/paintcursor.png'), 1, 16)
        # self.setCursor(self._cursor)

    def activate(self):
        super().activate()
        QApplication.setOverrideCursor(self._cursor)

    def deactivate(self):
        QApplication.restoreOverrideCursor()
        super().deactivate()
