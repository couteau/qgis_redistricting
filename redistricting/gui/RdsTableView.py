# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - QTableView with frozen columns -- 
    adapted from https://doc.qt.io/qt-6/qtwidgets-itemviews-frozencolumn-example.html

        begin                : 2024-05-18
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Cryptodira
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
from typing import (
    Optional,
    Union
)

from qgis.PyQt.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    Qt,
    pyqtProperty
)
from qgis.PyQt.QtGui import QResizeEvent
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableView,
    QWidget
)


class RdsTableView(QTableView):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._frozenColumnsView = QTableView(self)
        self._frozenColumnCount = 1

        self.init()

        self.horizontalHeader().sectionResized.connect(self.updateSectionWidth)
        self.verticalHeader().sectionResized.connect(self.updateSectionHeight)
        self._frozenColumnsView.verticalScrollBar().valueChanged.connect(self.verticalScrollBar().setValue)
        self.verticalScrollBar().valueChanged.connect(self._frozenColumnsView.verticalScrollBar().setValue)

    @pyqtProperty(int)
    def frozenColumnCount(self) -> int:
        return self._frozenColumnCount

    @frozenColumnCount.setter
    def frozenColumnCount(self, value: int):
        self._frozenColumnCount = value
        for col in range(self._frozenColumnCount):
            self._frozenColumnsView.setColumnHidden(col, False)
        self.updateFrozenTableGeometry()

    def init(self):
        self._frozenColumnsView.setFocusPolicy(Qt.NoFocus)
        self._frozenColumnsView.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._frozenColumnsView.verticalHeader().hide()
        self._frozenColumnsView.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)

        self.viewport().stackUnder(self._frozenColumnsView)

        self._frozenColumnsView.setStyleSheet("QTableView { border: none;}")
        self._frozenColumnsView.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._frozenColumnsView.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._frozenColumnsView.show()

        self.updateFrozenTableModel()

        self.setHorizontalScrollMode(QTableView.ScrollPerPixel)
        self.setVerticalScrollMode(QTableView.ScrollPerPixel)
        self._frozenColumnsView.setVerticalScrollMode(QTableView.ScrollPerPixel)

    def resizeEvent(self, e: QResizeEvent):
        super().resizeEvent(e)
        self.updateFrozenTableGeometry()

    def moveCursor(self, cursorAction: QAbstractItemView.CursorAction, modifiers: Union[Qt.KeyboardModifiers, Qt.KeyboardModifier]) -> QModelIndex:
        current = super().moveCursor(cursorAction, modifiers)
        if cursorAction == QTableView.MoveLeft and current.column() >= self._frozenColumnCount \
                and self.visualRect(current).topLeft().x() < self._frozenColumnsView.columnWidth(0):
            newValue = self.horizontalScrollBar().value() + self.visualRect(current).topLeft().x() - \
                self._frozenColumnsView.columnWidth(0)
            self.horizontalScrollBar().setValue(newValue)

        return current

    def scrollTo(self, index: QModelIndex, hint: QAbstractItemView.ScrollHint = QAbstractItemView.EnsureVisible):
        super().scrollTo(index, hint)

    def updateFrozenTableGeometry(self):
        width = sum(self.columnWidth(i) for i in range(self._frozenColumnCount)) - 2
        self._frozenColumnsView.setGeometry(
            self.verticalHeader().width() + self.frameWidth(),
            self.frameWidth(),
            width,
            self.viewport().height() + self.horizontalHeader().height()
        )
        if self.model() is not None:
            for col in range(self._frozenColumnCount, self.model().columnCount()):
                self._frozenColumnsView.setColumnHidden(col, True)

            for col in range(self._frozenColumnCount):
                self._frozenColumnsView.setColumnWidth(col, self.columnWidth(col))

    def updateSectionWidth(self, logicalIndex: int, oldSize: int, newSize: int):  # pylint: disable=unused-argument
        if (logicalIndex < self._frozenColumnCount):
            self._frozenColumnsView.setColumnWidth(logicalIndex, newSize)
            self.updateFrozenTableGeometry()

    def updateSectionHeight(self, logicalIndex: int, oldSize: int, newSize: int):  # pylint: disable=unused-argument
        self._frozenColumnsView.setRowHeight(logicalIndex, newSize)

    def updateFrozenTableModel(self):
        self._frozenColumnsView.setModel(self.model())
        if self.model() is not None:
            self._frozenColumnsView.setSelectionModel(self.selectionModel())
            self.updateFrozenTableGeometry()

    def setModel(self, model: Union[QAbstractItemModel, None]):
        super().setModel(model)
        self.updateFrozenTableModel()
