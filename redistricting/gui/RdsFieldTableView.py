# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - A QTableView with rows that can be drag/drop 
        reordered

        begin                : 2022-01-15
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
from typing import Union, Iterable, List

from qgis.PyQt.QtCore import Qt, QAbstractTableModel, QCoreApplication, QModelIndex, QVariant, pyqtSignal, pyqtProperty
from qgis.PyQt.QtWidgets import QWidget, QTableView, QAbstractItemView, QProxyStyle, QStyleOption
from qgis.PyQt.QtGui import QDropEvent, QDragMoveEvent, QMouseEvent
from qgis.core import QgsApplication
from ..core import Field, DataField, FieldList, BasePopulation

# TODO: come up with an accessible method for reordering without the mouse


class FieldListModel(QAbstractTableModel):

    _headings = [QCoreApplication.translate('Redistricting', 'Field'),
                 QCoreApplication.translate('Redistricting', 'Caption'),
                 QCoreApplication.translate('Redistricting', '∑'),
                 QCoreApplication.translate('Redistricting', '%Pop'),
                 QCoreApplication.translate('Redistricting', '%VAP'),
                 QCoreApplication.translate('Redistricting', '%CVAP')]

    def __init__(self, fields: Union[FieldList, List[Field]] = None, parent=None):
        super().__init__(parent)
        if isinstance(fields, FieldList):
            self._data: FieldList = fields[:]
            self._data.setParent(self)
        else:
            self._data: FieldList = FieldList(self, fields)
        self._colCount = 3
        if len(self._data) > 0:
            self.fieldType = type(self._data[0])
        else:
            self.fieldType = Field
        self._vapEnabled = True
        self._cvapEnabled = True

    @property
    def fields(self) -> List[Field]:
        return list(self._data)

    @fields.setter
    def fields(self, value: List[Field]):
        if len(value) == 0 and len(self._data) == 0:
            return
        if len(self._data):
            self.beginRemoveRows(QModelIndex(), 0, len(self._data))
            self._data.clear()
            self.endRemoveRows()
        if value is not None and len(value):
            self.beginInsertRows(QModelIndex(), 0, len(value))
            self._data.extend(value)
            self.fieldType = type(self._data[0])
            self.endInsertRows()

    @property
    def vapEnabled(self) -> bool:
        return self._vapEnabled

    @vapEnabled.setter
    def vapEnabled(self, value: bool):
        self._vapEnabled = value

    @property
    def cvapEnabled(self) -> bool:
        return self._cvapEnabled

    @cvapEnabled.setter
    def cvapEnabled(self, value: bool):
        self._cvapEnabled = value

    @property
    def fieldType(self):
        return self._fieldType

    @fieldType.setter
    def fieldType(self, value: type):
        self._fieldType = value
        self.setColCount(7 if self._fieldType == DataField else 3)

    def setColCount(self, value):
        if value != self._colCount:
            remove = value < self._colCount
            if remove:
                self.beginRemoveColumns(QModelIndex(), value - 1, self._colCount - 2)
            else:
                self.beginInsertColumns(QModelIndex(), self._colCount - 1, value - 2)
            self._colCount = value
            if remove:
                self.endRemoveColumns()
            else:
                self.endInsertColumns()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # pylint: disable=unused-argument
        return 0 if parent.isValid() else self._colCount

    def data(self, index: QModelIndex, role):
        row = index.row()
        col = index.column()

        if role in {Qt.DisplayRole, Qt.EditRole}:
            if col == self._colCount - 1:
                value = QVariant
            elif col == 0:
                value = self._data[row].field
            elif col == 1:
                value = self._data[row].caption
            else:
                value = QVariant()
        elif role == Qt.DecorationRole:
            if col == self._colCount - 1:
                value = QgsApplication.getThemeIcon("/mActionDeleteSelected.svg")
            elif col == 0:
                value = self._data[row].icon
            else:
                value = QVariant()
        elif role == Qt.CheckStateRole:
            field = self._data[row]
            if col == self._colCount - 1:
                value = QVariant()
            elif col == 2:
                value = Qt.Checked if field.sum else Qt.Unchecked
            elif col == 3:
                value = Qt.Checked if field.pctbase == BasePopulation.TOTALPOP else Qt.Unchecked
            elif col == 4:
                value = Qt.Checked if field.pctbase == BasePopulation.VAP and self._vapEnabled else Qt.Unchecked
            elif col == 5:
                value = Qt.Checked if field.pctbase == BasePopulation.CVAP and self._cvapEnabled else Qt.Unchecked
            else:
                value = QVariant()
        elif role == Qt.TextAlignmentRole:
            if col in range(2, 6):
                value = Qt.AlignCenter
            else:
                value = QVariant()
        elif role == Qt.AccessibleDescriptionRole:
            field = self._data[row]
            if col == self._colCount - 1:
                value = QCoreApplication.translate(
                    'Redistricting', 'Click to delete field {field}').format(field=field.fieldName)
            elif col == 2:
                value = QCoreApplication.translate('Redistricting', 'Display sum for field {field} is {checkstate}'). \
                    format(field=field.fieldName, checkstate='checked' if field.sum else 'unchecked')
            elif col == 3:
                value = QCoreApplication.translate(
                    'Redistricting',
                    'Display field {field} as percent of total population is {checkstate}'). \
                    format(field=field.fieldName,
                           checkstate='checked' if field.pctbase == BasePopulation.TOTALPOP else 'unchecked')
            elif col == 4:
                value = QCoreApplication.translate(
                    'Redistricting',
                    'Display field {field} as percent of voting age population is {checkstate}'). \
                    format(field=field.fieldName,
                           checkstate='checked' if field.pctbase == BasePopulation.VAP else 'unchecked')
            elif col == 5:
                value = QCoreApplication.translate(
                    'Redistricting',
                    'Display field {field} as percent of citizen voting age population is {checkstate}'). \
                    format(field=field.fieldName,
                           checkstate='checked' if field.pctbase == BasePopulation.CVAP else 'unchecked')
            else:
                value = QVariant()
        else:
            value = QVariant()

        return value

    def headerData(self, section, orientation: Qt.Orientation, role):
        if role == Qt.DisplayRole and section != self._colCount - 1:
            if orientation == Qt.Horizontal:
                value = self._headings[section]
            else:
                value = str(section+1)
        else:
            value = QVariant()

        return value

    def setData(self, index, value, role):
        if not index.isValid() or index.column() in {0, self._colCount - 1}:
            return False

        field = self._data[index.row()]
        if role == Qt.EditRole and index.column() == 1:
            field.caption = value
            return True

        if role == Qt.CheckStateRole:
            if index.column() == 2:
                field.sum = bool(value)
                return True

            if index.column() == 3:
                if value:
                    if field.pctbase == BasePopulation.VAP:
                        self.dataChanged.emit(self.createIndex(index.row(), 4),
                                              self.createIndex(index.row(), 4),
                                              [Qt.CheckStateRole])
                    elif field.pctbase == BasePopulation.CVAP:
                        self.dataChanged.emit(self.createIndex(index.row(), 5),
                                              self.createIndex(index.row(), 5),
                                              [Qt.CheckStateRole])
                    field.pctbase = BasePopulation.TOTALPOP
                elif field.pctbase == BasePopulation.TOTALPOP:
                    field.pctbase = BasePopulation.NOPCT
                return True

            if index.column() == 4 and self._vapEnabled:
                if value:
                    if field.pctbase == BasePopulation.TOTALPOP:
                        self.dataChanged.emit(self.createIndex(index.row(), 3),
                                              self.createIndex(index.row(), 3),
                                              [Qt.CheckStateRole])
                    elif field.pctbase == BasePopulation.CVAP:
                        self.dataChanged.emit(self.createIndex(index.row(), 5),
                                              self.createIndex(index.row(), 5),
                                              [Qt.CheckStateRole])
                    field.pctbase = BasePopulation.VAP
                elif field.pctbase == BasePopulation.VAP:
                    field.pctbase = BasePopulation.NOPCT
                return True

            if index.column() == 5 and self._cvapEnabled:
                if value:
                    if field.pctbase == BasePopulation.TOTALPOP:
                        self.dataChanged.emit(self.createIndex(index.row(), 3),
                                              self.createIndex(index.row(), 3),
                                              [Qt.CheckStateRole])
                    elif field.pctbase == BasePopulation.VAP:
                        self.dataChanged.emit(self.createIndex(index.row(), 4),
                                              self.createIndex(index.row(), 4),
                                              [Qt.CheckStateRole])
                    field.pctbase = BasePopulation.CVAP
                elif field.pctbase == BasePopulation.CVAP:
                    field.pctbase = BasePopulation.NOPCT
                return True

        return False

    def flags(self, index):
        f = super().flags(index)
        if not index.isValid():
            return f | Qt.ItemIsDropEnabled

        if index.row() < len(self._data):
            f = f | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled

        if index.row() >= len(self._data) or index.column() == 0 or index.column() == self._colCount - 1:
            return f

        if index.column() == 1:
            f = f | Qt.ItemIsEditable
        elif self._data[index.row()].isNumeric:
            if index.column() == 2 or index.column() == 3:
                f = f | Qt.ItemIsUserCheckable
            elif index.column() == 4:
                if self._vapEnabled:
                    f = f | Qt.ItemIsUserCheckable
                else:
                    f = f & ~Qt.ItemIsEnabled
            elif index.column() == 5:
                if self._cvapEnabled:
                    f = f | Qt.ItemIsUserCheckable
                else:
                    f = f & ~Qt.ItemIsEnabled

        return f

    def appendField(self, layer, field, isExpression=False, caption=None):
        for f in self._data:
            if f.field == field:
                return

        self.beginInsertRows(QModelIndex(), len(self._data), len(self._data))
        self._data.append(self._fieldType(layer, field, isExpression, caption))
        self.endInsertRows()

    def deleteField(self, row):
        self.beginRemoveRows(QModelIndex(), row, row)
        self._data.remove(self._data[row])
        self.endRemoveRows()

    def supportedDropActions(self):
        return Qt.MoveAction | Qt.CopyAction

    def moveField(self, row_source, row_target):
        row_a, row_b = max(row_source, row_target), min(row_source, row_target)
        self.beginMoveRows(QModelIndex(), row_a, row_a, QModelIndex(), row_b)
        self._data.move(row_a, row_b)
        self.endMoveRows()


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

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setModel(FieldListModel(parent=self))
        self.canDelete = True
        self.pressIndex = None

    def model(self) -> FieldListModel:
        return self._model

    def setModel(self, value: FieldListModel):
        self._model = value
        super().setModel(value)

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

    def startDrag(self, supportedActions: Union[Qt.DropActions, Qt.DropAction]):
        super().startDrag(supportedActions)

    def dragMoveEvent(self, e: QDragMoveEvent):
        super().dragMoveEvent(e)

    def dataChanged(self, topLeft: QModelIndex, bottomRight: QModelIndex, roles: Iterable[int] = None):
        super().dataChanged(topLeft, bottomRight, roles)
        self.fieldsChanged.emit(self.model().fields)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            index = self.indexAt(e.pos())
            if index.isValid():
                self.pressIndex = index
        return super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton and self.canDelete:
            index = self.indexAt(e.pos())
            if index.isValid() and index == self.pressIndex and index.column() == self._model.columnCount() - 1:
                self._model.deleteField(index.row())
        self.pressIndex = None
        return super().mouseReleaseEvent(e)

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
