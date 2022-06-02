# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RdFieldTableView
        A QTableView with rows that can be drag/drop reordered
                                
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

from typing import Iterable, List
from qgis.PyQt.QtCore import Qt, QModelIndex, pyqtSignal, pyqtProperty
from qgis.PyQt.QtWidgets import QTableView, QAbstractItemView, QProxyStyle, QStyleOption
from qgis.PyQt.QtGui import QDropEvent
from ..core import Field

# TODO: come up with an accessible method for reordering without the mouse


class RdsFieldTableView(QTableView):

    class DropmarkerStyle(QProxyStyle):
        def drawPrimitive(self, element, option, painter, widget=None):
            """Draw a line across the entire row rather than just the column we're hovering over.
            This may not always work depending on global style - for instance I think it won't
            work on OSX."""
            if element == self.PE_IndicatorItemViewItemDrop and not option.rect.isNull():
                option_new = QStyleOption(option)
                option_new.rect.setLeft(0)
                if widget:
                    option_new.rect.setRight(widget.width())
                option = option_new
            super().drawPrimitive(element, option, painter, widget)

    fieldsChanged = pyqtSignal(list, name='fieldsChanged')

    def setEnableDragRows(self, enable: bool):
        if enable:
            self.verticalHeader().hide()
            self.setSelectionBehavior(self.SelectRows)
            self.setSelectionMode(self.SingleSelection)
            self.setDragDropMode(self.InternalMove)
            self.setDragDropOverwriteMode(False)
            self.setStyle(self.DropmarkerStyle())

    def dropEvent(self, event: QDropEvent):
        if (event.source() is not self or
            (event.dropAction() != Qt.MoveAction and
             self.dragDropMode() != QAbstractItemView.InternalMove)):
            super().dropEvent(event)

        selection = self.selectedIndexes()
        from_index = selection[0].row() if selection else -1
        to_index = self.indexAt(event.pos()).row()
        if (0 <= from_index < self.model().rowCount() and
            0 <= to_index < self.model().rowCount() and
                from_index != to_index):
            self.model().moveField(from_index, to_index)
            event.accept()
        super().dropEvent(event)

    def dataChanged(self, topLeft: QModelIndex, bottomRight: QModelIndex, roles: Iterable[int] = ...) -> None:
        super().dataChanged(topLeft, bottomRight, roles)
        self.fieldsChanged.emit(self.model().fields)

    @pyqtProperty(list, notify=fieldsChanged)
    def fields(self) -> List[Field]:
        m = self.model()
        if hasattr(m, 'fields'):
            return m.fields
        return []

    @fields.setter
    def fields(self, value: list):
        m = self.model()
        if hasattr(m, 'fields'):
            m.fields = value
