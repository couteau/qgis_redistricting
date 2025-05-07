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

from collections.abc import Iterable
from typing import Union

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QAbstractTableModel, QCoreApplication, QModelIndex, Qt, QVariant, pyqtProperty, pyqtSignal
from qgis.PyQt.QtGui import QDropEvent, QMouseEvent
from qgis.PyQt.QtWidgets import QAbstractItemView, QProxyStyle, QStyleOption, QTableView, QWidget

from ..models import RdsDataField, RdsField
from ..utils import tr

# TODO: come up with an accessible method for reordering without the mouse


class FieldListModel(QAbstractTableModel):
    _headings = [
        tr("Redistricting", "RdsField"),
        tr("Redistricting", "Caption"),
        tr("Redistricting", "∑"),
        tr("Redistricting", "%"),
    ]

    def __init__(self, fields: list[RdsField] = None, popFields: list[RdsField] = None, parent=None):
        super().__init__(parent)
        if fields is None:
            self._data: list[Union[RdsField, RdsDataField]] = []
        else:
            self._data: list[Union[RdsField, RdsDataField]] = fields[:]

        self.popFields = popFields
        self._colCount = 3
        if self._data:
            self.fieldType = type(self._data[0])
        else:
            self.fieldType = RdsField

    @pyqtProperty(list)
    def fields(self):
        return self._data

    @fields.setter
    def fields(self, value: list[RdsField]):
        if len(value) == 0 and len(self._data) == 0:
            return
        if len(self._data) > 0:
            self.beginRemoveRows(QModelIndex(), 0, len(self._data))
            self._data.clear()
            self.endRemoveRows()
        if value is not None and len(value):
            self.beginInsertRows(QModelIndex(), 0, len(value))
            self._data = value
            self.fieldType = type(self._data[0])
            self.endInsertRows()

    @property
    def fieldType(self):
        return self._fieldType

    @fieldType.setter
    def fieldType(self, value: type[RdsField]):
        self._fieldType = value
        self.setColCount(5 if self._fieldType == RdsDataField else 3)

    @property
    def popFields(self) -> dict[str, RdsField]:
        return self._popFields

    @popFields.setter
    def popFields(self, value: list[RdsField]):
        if value is None:
            self._popFields: dict[str, RdsField] = {}
        else:
            self._popFields = {fld.field: fld for fld in value}

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

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else self._colCount

    def data(self, index: QModelIndex, role):  # noqa: PLR0912, PLR0915
        row = index.row()
        col = index.column()

        if role in {Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole}:
            if col == self._colCount - 1:
                value = QVariant
            elif col == 0:
                value = self._data[row].field
            elif col == 1:
                value = self._data[row].caption
            elif col == 3:
                pctbase = self._data[row].pctBase
                if pctbase and pctbase in self.popFields:
                    value = self.popFields[self._data[row].pctBase].caption
                else:
                    value = QVariant()
            else:
                value = QVariant()
        elif role == Qt.ItemDataRole.DecorationRole:
            if col == self._colCount - 1:
                value = QgsApplication.getThemeIcon("/mActionDeleteSelected.svg")
            elif col == 0:
                value = self._data[row].icon
            else:
                value = QVariant()
        elif role == Qt.ItemDataRole.CheckStateRole:
            field = self._data[row]
            if col == self._colCount - 1:
                value = QVariant()
            elif col == 2:
                value = Qt.CheckState.Checked if field.sumField else Qt.CheckState.Unchecked
            else:
                value = QVariant()
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in {2, 4}:
                value = Qt.AlignmentFlag.AlignCenter
            else:
                value = QVariant()
        elif role == Qt.ItemDataRole.AccessibleDescriptionRole:
            field = self._data[row]
            if col == self._colCount - 1:
                value = QCoreApplication.translate("Redistricting", "Click to delete field {field}").format(
                    field=field.fieldName
                )
            elif col == 2:
                value = QCoreApplication.translate(
                    "Redistricting", "Display sum for field {field} is {checkstate}"
                ).format(field=field.fieldName, checkstate="checked" if field.sumField else "unchecked")
            elif col == 3:
                pctbase = self._data[row].pctBase
                if pctbase and pctbase in self.popFields:
                    basefield = self.popFields[self._data[row].pctBase].caption
                else:
                    basefield = None
                if basefield is None:
                    value = QCoreApplication.translate(
                        "Redistricting", "Do not display field {field} as a percentage"
                    ).format(field=field.fieldName, basefield=basefield)
                else:
                    value = QCoreApplication.translate(
                        "Redistricting", "Display field {field} as percent of {basefield}"
                    ).format(field=field.fieldName, basefield=basefield)
            else:
                value = QVariant()
        else:
            value = QVariant()

        return value

    def headerData(self, section, orientation: Qt.Orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and section != self._colCount - 1:
            if orientation == Qt.Orientation.Horizontal:
                value = self._headings[section]
            else:
                value = str(section + 1)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if section in range(2, 4):
                value = Qt.AlignmentFlag.AlignCenter
            else:
                value = QVariant()
        else:
            value = QVariant()

        return value

    def setData(self, index, value, role):
        if not index.isValid() or index.column() in {0, self._colCount - 1}:
            return False

        field = self._data[index.row()]
        if role == Qt.ItemDataRole.EditRole:
            if index.column() == 1:
                field.caption = value
                return True

            if index.column() == 3:
                if 0 <= value < len(self._popFields):
                    field.pctBase = list(self._popFields.values())[value].fieldName
                    return True

        if role == Qt.ItemDataRole.CheckStateRole:
            if index.column() == 2:
                field.sumField = bool(value)
                return True

        return False

    def flags(self, index):
        f = super().flags(index)
        if not index.isValid():
            return f | Qt.ItemFlag.ItemIsDropEnabled

        if index.row() < len(self._data):
            f = f | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled

        if index.row() >= len(self._data) or index.column() == 0 or index.column() == self._colCount - 1:
            return f

        if index.column() == 1:
            f = f | Qt.ItemFlag.ItemIsEditable
        elif self._data[index.row()].isNumeric:
            if index.column() == 2:
                f = f | Qt.ItemFlag.ItemIsUserCheckable
            elif index.column() == 3:
                f = f | Qt.ItemFlag.ItemIsEditable

        return f

    def appendField(self, layer, field, caption=None) -> Union[RdsField, RdsDataField, None]:
        for f in self._data:
            if f.field == field:
                return None

        fld = self._fieldType(layer, field, caption)

        self.beginInsertRows(QModelIndex(), len(self._data), len(self._data))
        self._data.append(fld)
        self.endInsertRows()
        return fld

    def deleteField(self, row):
        self.beginRemoveRows(QModelIndex(), row, row)
        self._data.remove(self._data[row])
        self.endRemoveRows()

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction

    def moveField(self, row_source, row_target):
        if 0 <= row_source < len(self._data) and 0 <= row_target < len(self._data):
            self.beginMoveRows(QModelIndex(), row_source, row_source, QModelIndex(), row_target)
            item = self._data[row_source]
            del self._data[row_source]
            self._data.insert(row_target, item)
            self.endMoveRows()
        else:
            raise ValueError(tr("Source and target rows must be in list"))


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

    fieldsChanged = pyqtSignal(list, name="fieldsChanged")

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
            self.setSelectionBehavior(self.SelectionBehavior.SelectRows)
            self.setSelectionMode(self.SelectionMode.SingleSelection)
            self.setDragDropMode(self.DragDropMode.InternalMove)
            self.setDragDropOverwriteMode(False)
            self.setStyle(self.DropmarkerStyle())

    def dropEvent(self, event: QDropEvent):
        if event.source() is not self or (
            event.dropAction() != Qt.DropAction.MoveAction
            and self.dragDropMode() != QAbstractItemView.DragDropMode.InternalMove
        ):
            super().dropEvent(event)

        selection = self.selectedIndexes()
        from_index = selection[0].row() if selection else -1
        to_index = self.indexAt(event.pos()).row()
        if (
            0 <= from_index < self.model().rowCount()
            and 0 <= to_index < self.model().rowCount()
            and from_index != to_index
        ):
            self.model().moveField(from_index, to_index)
            event.accept()
        super().dropEvent(event)

    def dataChanged(self, topLeft: QModelIndex, bottomRight: QModelIndex, roles: Iterable[int] = None):
        super().dataChanged(topLeft, bottomRight, roles)
        self.fieldsChanged.emit(self.model().fields)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(e.pos())
            if index.isValid():
                self.pressIndex = index
        return super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton and self.canDelete:
            index = self.indexAt(e.pos())
            if index.isValid() and index == self.pressIndex and index.column() == self._model.columnCount() - 1:
                self._model.deleteField(index.row())
        self.pressIndex = None
        return super().mouseReleaseEvent(e)

    @pyqtProperty(list, notify=fieldsChanged)
    def fields(self) -> list[RdsField]:
        m = self.model()
        if not isinstance(m, FieldListModel):
            return []

        return m.fields

    @fields.setter
    def fields(self, value: list):
        m = self.model()
        if isinstance(m, FieldListModel):
            m.fields = value
