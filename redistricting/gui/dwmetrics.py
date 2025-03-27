# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - QDockWidget displaying plan metrics

        begin                : 2024-09-20
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
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import (
    Qt,
    pyqtSignal
)
from qgis.PyQt.QtGui import QMouseEvent
from qgis.PyQt.QtWidgets import QHeaderView

from .rdsdockwidget import RdsDockWidget
from .ui.PlanMetrics import Ui_qdwPlanMetrics


class QResizableHeaderView(QHeaderView):
    resized = pyqtSignal()

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setSectionsClickable(True)
        self.setStretchLastSection(True)
        self.setHighlightSections(True)
        self.setMouseTracking(True)
        self.resizing = False
        self.resize_offset = 0
        self.old_size = 0

    def mousePressEvent(self, e: QMouseEvent):
        atEdge = e.x() > self.rect().right() - 10 if self.orientation() == Qt.Vertical else e.y() > self.rect().bottom() - 10
        if atEdge:
            self.resize_offset = self.rect().right() - e.pos().x() if self.orientation() == Qt.Vertical else self.rect().bottom() - e.pos().y()
            self.old_size = self.width() if self.orientation() == Qt.Vertical else self.height()
            self.resizing = True

        return super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        if self.resizing:
            if self.orientation() == Qt.Vertical:
                self.setFixedWidth(e.x() - self.rect().left() + self.resize_offset)
            else:
                self.setFixedHeight(e.y() - self.rect().top() + self.resize_offset)
        else:
            super().mouseMoveEvent(e)

        if not self.testAttribute(Qt.WA_SetCursor):
            pos = e.x() if self.orientation() == Qt.Vertical else e.y()
            atEdge = pos > self.rect().right() - 10 \
                if self.orientation() == Qt.Vertical \
                else pos > self.rect().bottom() - 10

            if atEdge:
                self.setCursor(Qt.SplitHCursor if self.orientation() == Qt.Vertical else Qt.SplitVCursor)
            else:
                self.unsetCursor()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if self.resizing:
            if self.orientation() == Qt.Vertical:
                self.setFixedWidth(e.x() - self.rect().left() + self.resize_offset)
            else:
                self.setFixedHeight(e.y() - self.rect().top() + self.resize_offset)
            self.resizing = False
            self.resized.emit()

        return super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape and self.resizing:
            self.resizing = False
            if self.orientation() == Qt.Vertical:
                self.setFixedWidth(self.old_size)
            else:
                self.setFixedHeight(self.old_size)

        return super().keyPressEvent(e)


class DockPlanMetrics(Ui_qdwPlanMetrics, RdsDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.header = QResizableHeaderView(Qt.Vertical, self.tblPlanMetrics)
        self.header.resized.connect(self.tblPlanMetrics.updateGeometries)
        self.tblPlanMetrics.setVerticalHeader(self.header)

        self.lblWaiting.setParent(self.tblPlanMetrics)
        self.btnHelp.setIcon(QgsApplication.getThemeIcon('/mActionHelpContents.svg'))
        self.btnHelp.clicked.connect(self.btnHelpClicked)
